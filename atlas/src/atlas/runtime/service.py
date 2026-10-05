"""ATLAS service facade: startup/recovery, state transitions, audit.

All state changes go through ``_append`` → event store → projection. The in-memory
projection is a cache of the event log, rebuilt from scratch on every start.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from atlas.config.loader import LoadedConfig, load_config
from atlas.config.models import ConfigError
from atlas.domain.enums import Direction, Provenance, RiskVerdict, RuntimeMode, RuntimeState
from atlas.domain.money import to_dec
from atlas.domain.schemas import Position, RiskDecision, TradeCandidate, model_to_payload
from atlas.events.model import EventType, NewEvent, Priority, StoredEvent
from atlas.ledger.capital import LedgerError, allocate
from atlas.risk.engine import RiskEngine, SnapshotVerifier
from atlas.risk.state import RiskState, build_risk_state
from atlas.runtime.clock import Clock, SystemClock
from atlas.runtime.logging_setup import get_logger, log
from atlas.state.projection import AtlasState, replay
from atlas.state.store import AppendResult, EventStore, state_hash
from atlas.version import ATLAS_VERSION, PHASE, RISK_ENGINE_VERSION

DB_NAME = "atlas.sqlite3"


class AtlasError(Exception):
    pass


class AtlasHalted(AtlasError):
    """Refused because the runtime is halted for an integrity reason."""


class NotInitialized(AtlasError):
    pass


@dataclass(frozen=True)
class RecoveryStep:
    name: str
    status: str  # OK | HALT | NOT_AVAILABLE
    detail: str


@dataclass
class RecoveryReport:
    steps: list[RecoveryStep] = field(default_factory=list)
    runtime_state: RuntimeState = RuntimeState.OFFLINE
    halt_reasons: list[str] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str) -> None:
        self.steps.append(RecoveryStep(name, status, detail))
        if status == "HALT":
            self.halt_reasons.append(f"{name}: {detail}")

    def as_payload(self) -> dict[str, Any]:
        return {
            "runtime_state": self.runtime_state.value,
            "halt_reasons": self.halt_reasons,
            "steps": [{"name": s.name, "status": s.status, "detail": s.detail} for s in self.steps],
        }


class Atlas:
    def __init__(
        self,
        root: Path | str,
        home: Path | str,
        clock: Clock | None = None,
        verifier: SnapshotVerifier | None = None,
        config_dir: str = "config",
    ):
        self.root = Path(root)
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.clock = clock or SystemClock()
        self.loaded: LoadedConfig = load_config(self.root, config_dir)
        self.cfg = self.loaded.config
        self.store = EventStore(self.home / DB_NAME, self.clock, ATLAS_VERSION)
        self.store.set_config_context(self.loaded.version_label, self.loaded.fingerprint)
        self.engine = RiskEngine(self.cfg, self.loaded.instruments, verifier)
        self.logger = get_logger(self.home)
        self.runtime_state = RuntimeState.OFFLINE
        self.state: AtlasState = AtlasState(tz_offset_minutes=self.cfg.runtime.timezone_offset_minutes)
        self.last_report: RecoveryReport | None = None
        self._integrity_halt = False

    # ================================================================== lifecycle
    @property
    def initialized(self) -> bool:
        return self.state.ledger.initialized

    def init(self, reason: str = "initial configuration") -> RecoveryReport:
        if self.store.count() > 0:
            raise AtlasError("event store already contains events; refusing to re-initialize")
        self._raw_append(self._config_approval_event(reason, previous=None))
        self._raw_append(
            NewEvent(
                EventType.LEDGER_INITIALIZED,
                {
                    "initial_capital": str(self.cfg.capital.initial_trading_capital),
                    "currency": self.cfg.capital.currency,
                },
                idempotency_key="ledger:init",
            )
        )
        return self.start()

    def start(self, record: bool = True) -> RecoveryReport:
        """Load → verify → replay → reconcile → recalc risk → READY or HALTED."""
        self.runtime_state = RuntimeState.STARTING
        self._integrity_halt = False
        rep = RecoveryReport()
        rep.add(
            "load_configuration",
            "OK",
            f"{self.loaded.version_label} fingerprint {self.loaded.fingerprint[:12]} "
            f"mode={self.cfg.runtime.mode.value}",
        )

        if self.store.count() == 0:
            rep.add("load_state", "NOT_AVAILABLE", "empty event store — run `atlas init`")
            rep.runtime_state = RuntimeState.OFFLINE
            self.runtime_state = RuntimeState.OFFLINE
            self.last_report = rep
            return rep

        chain = self.store.verify_chain()
        if chain.ok:
            rep.add("verify_event_chain", "OK", f"{chain.events_checked} events, hash chain intact")
        else:
            self._integrity_halt = True
            rep.add("verify_event_chain", "HALT", f"seq {chain.broken_at_seq}: {chain.detail}")

        self.state = replay(self.store.iter_events(), self.cfg.runtime.timezone_offset_minutes)
        errs = self.state.integrity_errors()
        if errs:
            self._integrity_halt = True
            rep.add("replay_state", "HALT", "; ".join(errs))
        else:
            rep.add("replay_state", "OK", f"replayed to seq {self.state.last_seq}")

        snap = self.store.latest_snapshot()
        if snap is None:
            rep.add("compare_snapshot", "NOT_AVAILABLE", "no snapshot yet")
        else:
            at_snap = replay(self.store.iter_events(snap.event_seq), self.cfg.runtime.timezone_offset_minutes)
            recomputed = state_hash(at_snap.to_dict())
            if recomputed == snap.state_hash and state_hash(snap.state) == snap.state_hash:
                rep.add("compare_snapshot", "OK", f"snapshot @seq {snap.event_seq} matches replay")
            else:
                self._integrity_halt = True
                rep.add("compare_snapshot", "HALT", f"snapshot @seq {snap.event_seq} != replayed state")

        self._check_config_approval(rep)

        rep.add(
            "reconcile_account",
            "NOT_AVAILABLE",
            "no execution venue in Phase 1; capital ledger is the sole source",
        )
        rep.add("reconcile_orders", "NOT_AVAILABLE", "no order subsystem in Phase 1; no orders can exist")
        self._reconcile_positions(rep)
        rep.add("validate_market_data", "NOT_AVAILABLE", "no market-data adapter in Phase 1")

        if self.initialized and not self._integrity_halt:
            rs = self.risk_state()
            rep.add(
                "recalculate_risk",
                "OK",
                f"mode={rs.mode.value} per-trade budget={rs.per_trade_budget:.2f} "
                f"daily headroom={rs.daily_headroom:.2f}",
            )
            if rs.kill_switch:
                rep.add("kill_switch", "HALT", f"kill switch active: {self.state.kill_reason}")
        else:
            rep.add(
                "recalculate_risk",
                "HALT" if self._integrity_halt else "NOT_AVAILABLE",
                "skipped: state integrity not established" if self._integrity_halt else "not initialized",
            )

        rep.runtime_state = RuntimeState.HALTED if rep.halt_reasons else RuntimeState.READY
        self.runtime_state = rep.runtime_state
        self.last_report = rep
        if record:
            etype = EventType.RUNTIME_HALTED if rep.halt_reasons else EventType.RUNTIME_STARTED
            if self._integrity_halt:
                etype = EventType.INTEGRITY_FAILURE
            self._raw_append(NewEvent(etype, rep.as_payload(), priority=None))
            if not self._integrity_halt:
                self._snapshot()
        log(
            self.logger,
            logging.WARNING if rep.halt_reasons else logging.INFO,
            "runtime start",
            **rep.as_payload(),
        )
        return rep

    def close(self) -> None:
        self.store.close()
        for h in list(self.logger.handlers):
            h.close()
            self.logger.removeHandler(h)
        self.runtime_state = RuntimeState.OFFLINE

    # ================================================================== recovery helpers
    def _check_config_approval(self, rep: RecoveryReport) -> None:
        ap = self.state.approved_config
        cur_v, cur_c, fp = (
            self.cfg.config_version,
            self.loaded.constitution.version,
            self.loaded.fingerprint,
        )
        if ap is None:
            rep.add("config_approval", "HALT", "no approved configuration recorded")
        elif ap["fingerprint"] == fp:
            rep.add("config_approval", "OK", f"config {cur_v} / constitution {cur_c} approved")
        elif ap["config_version"] == cur_v and ap["constitution_version"] == cur_c:
            rep.add(
                "config_approval",
                "HALT",
                "configuration changed WITHOUT a version bump — revert it, or bump "
                "config_version/constitution version and run `atlas config approve`",
            )
        else:
            rep.add(
                "config_approval",
                "HALT",
                f"new config {cur_v}/{cur_c} (approved: {ap['config_version']}/"
                f"{ap['constitution_version']}) awaits `atlas config approve`",
            )

    def _reconcile_positions(self, rep: RecoveryReport) -> None:
        positions = list(self.state.open_positions.values())
        bad = [
            p
            for p in positions
            if p.provenance is not Provenance.SYNTHETIC
            or self.cfg.runtime.mode is not RuntimeMode.SIMULATION
        ]
        if bad:
            ids = ", ".join(p.position_id for p in bad)
            rep.add("reconcile_positions", "HALT", f"position(s) {ids} cannot be reconciled to any venue")
        else:
            rep.add(
                "reconcile_positions",
                "OK",
                f"{len(positions)} open position(s) (synthetic simulation positions only)",
            )

    # ================================================================== append plumbing
    def _raw_append(self, new: NewEvent) -> AppendResult:
        res = self.store.append(new)
        if not res.duplicate:
            self.state.apply(res.event)
        return res

    def _append(self, new: NewEvent) -> AppendResult:
        if self._integrity_halt:
            raise AtlasHalted("runtime HALTED for integrity; state writes refused")
        res = self._raw_append(new)
        if res.duplicate:
            self._raw_append(
                NewEvent(
                    EventType.DUPLICATE_SUPPRESSED,
                    {"idempotency_key": new.idempotency_key, "original_seq": res.event.seq},
                )
            )
        errs = self.state.integrity_errors()
        if errs:
            self._integrity_halt = True
            self.runtime_state = RuntimeState.HALTED
            self._raw_append(NewEvent(EventType.INTEGRITY_FAILURE, {"errors": errs}))
            raise AtlasHalted("; ".join(errs))
        return res

    def _snapshot(self) -> None:
        self.store.write_snapshot(self.state.last_seq, self.state.to_dict())

    def _require_initialized(self) -> None:
        if not self.initialized:
            raise NotInitialized("ATLAS is not initialized — run `atlas init`")

    def _config_approval_event(self, reason: str, previous: dict | None) -> NewEvent:
        return NewEvent(
            EventType.CONFIG_APPROVED,
            {
                "config_version": self.cfg.config_version,
                "constitution_version": self.loaded.constitution.version,
                "fingerprint": self.loaded.fingerprint,
                "reason": reason,
                "previous": previous,
                "constitution": self.loaded.constitution.model_dump(mode="json"),
                "config": self.cfg.model_dump(mode="json"),
            },
            priority=Priority.P1,
        )

    # ================================================================== queries
    def now(self) -> datetime:
        return self.clock.now_utc()

    def risk_state(self) -> RiskState:
        self._require_initialized()
        return build_risk_state(self.state, self.cfg, self.now())

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "atlas_version": ATLAS_VERSION,
            "phase": PHASE,
            "risk_engine_version": RISK_ENGINE_VERSION,
            "config": self.loaded.version_label,
            "mode": self.cfg.runtime.mode.value,
            "runtime_state": self.runtime_state.value,
            "halt_reasons": list(self.last_report.halt_reasons) if self.last_report else [],
            "events": self.store.count(),
            "initialized": self.initialized,
        }
        if self.initialized and not self._integrity_halt:
            rs = self.risk_state()
            out.update(
                {
                    "trading_capital": rs.trading_capital,
                    "reserve": rs.reserve,
                    "peak_trading_capital": rs.peak_trading_capital,
                    "drawdown_pct": rs.drawdown_pct,
                    "risk_mode": rs.mode.value,
                    "mode_reasons": list(rs.mode_reasons),
                    "effective_risk_pct": rs.effective_risk_pct,
                    "per_trade_budget": rs.per_trade_budget,
                    "daily_loss_ceiling": rs.daily_loss_ceiling,
                    "daily_realized_pnl": rs.daily_realized_pnl,
                    "daily_headroom": rs.daily_headroom,
                    "open_positions": len(rs.open_positions),
                    "max_positions": self.cfg.risk.max_concurrent_positions,
                    "consecutive_losses": rs.consecutive_losses,
                    "kill_switch": rs.kill_switch,
                }
            )
        return out

    # ================================================================== commands
    def deposit(self, amount: Decimal | str, note: str = "") -> StoredEvent:
        self._require_initialized()
        amt = to_dec(amount)
        trial = copy.deepcopy(self.state.ledger)
        trial.deposit(amt)  # raises LedgerError before anything is written
        ev = self._append(NewEvent(EventType.DEPOSIT, {"amount": str(amt), "note": note})).event
        self._snapshot()
        return ev

    def withdraw(self, amount: Decimal | str, source: str, note: str = "") -> StoredEvent:
        """Manual withdrawal only. There is no automated withdrawal path."""
        self._require_initialized()
        amt = to_dec(amount)
        src = source.upper()
        trial = copy.deepcopy(self.state.ledger)
        trial.withdraw(amt, src)
        ev = self._append(
            NewEvent(EventType.WITHDRAWAL, {"amount": str(amt), "source": src, "note": note})
        ).event
        self._snapshot()
        return ev

    def set_kill_switch(self, active: bool, reason: str) -> RecoveryReport:
        self._require_initialized()
        if not reason.strip():
            raise AtlasError("a reason is required to change the kill switch")
        self._append(
            NewEvent(EventType.KILL_SWITCH_SET, {"active": active, "reason": reason}, priority=Priority.P0)
        )
        return self.start()

    def approve_config(self, reason: str) -> RecoveryReport:
        self._require_initialized()
        if not reason.strip():
            raise AtlasError("a reason is required to approve a configuration")
        ap = self.state.approved_config
        if ap and ap["fingerprint"] == self.loaded.fingerprint:
            raise AtlasError("current configuration is already approved")
        if (
            ap
            and ap["config_version"] == self.cfg.config_version
            and ap["constitution_version"] == self.loaded.constitution.version
        ):
            raise ConfigError("configuration content changed but version did not — bump the version first")
        self._append(self._config_approval_event(reason, previous=ap))
        return self.start()

    def evaluate(self, cand: TradeCandidate) -> tuple[RiskDecision, bool]:
        """Record the candidate, run the Risk Engine, record the decision.

        Returns (decision, duplicate). A re-submitted candidate_id never produces a second
        decision: the original decision is returned and the duplicate is audited.
        """
        self._require_initialized()
        res = self._append(
            NewEvent(
                EventType.CANDIDATE_RECEIVED,
                {"candidate_id": cand.candidate_id, "candidate": model_to_payload(cand)},
                idempotency_key=f"candidate:{cand.candidate_id}",
            )
        )
        if res.duplicate:
            prior = self.store.get_by_idempotency_key(f"decision:{cand.candidate_id}")
            if prior is None:
                raise AtlasError(f"candidate {cand.candidate_id} recorded without a decision")
            self._snapshot()
            return RiskDecision.model_validate(prior.payload["decision"]), True
        decision = self.engine.evaluate(cand, self.risk_state(), self.runtime_state, self.now())
        self._append(
            NewEvent(
                EventType.RISK_DECISION,
                {
                    "candidate_id": cand.candidate_id,
                    "verdict": decision.verdict.value,
                    "codes": sorted(c.value for c in decision.codes()),
                    "decision": model_to_payload(decision),
                },
                idempotency_key=f"decision:{cand.candidate_id}",
                priority=Priority.P2,
            )
        )
        self._snapshot()
        log(
            self.logger,
            logging.INFO,
            "risk decision",
            candidate_id=cand.candidate_id,
            verdict=decision.verdict.value,
            codes=sorted(c.value for c in decision.codes()),
        )
        return decision, False

    # ================================================================== simulation fixtures
    # Phase 1 has no execution venue. These helpers exist ONLY so the Risk Engine's
    # portfolio-dependent rules (max positions, correlation, daily loss, streaks, profit
    # allocation) can be exercised. They refuse to run outside SIMULATION mode and only
    # accept SYNTHETIC positions.

    def _require_simulation(self) -> None:
        if self.cfg.runtime.mode is not RuntimeMode.SIMULATION:
            raise AtlasError("simulation fixtures are disabled outside SIMULATION mode")
        if self.runtime_state is not RuntimeState.READY:
            raise AtlasError(f"runtime is {self.runtime_state.value}")

    def open_simulated_position(self, position: Position) -> StoredEvent:
        self._require_initialized()
        self._require_simulation()
        if position.provenance is not Provenance.SYNTHETIC:
            raise AtlasError("only SYNTHETIC positions may be opened in Phase 1")
        ev = self._append(
            NewEvent(
                EventType.POSITION_OPENED,
                {"position": model_to_payload(position), "simulated": True},
                idempotency_key=f"position:{position.position_id}",
            )
        ).event
        self._snapshot()
        return ev

    def open_simulated_from_decision(
        self, cand: TradeCandidate, decision: RiskDecision, position_id: str | None = None
    ) -> StoredEvent:
        if decision.verdict is not RiskVerdict.RISK_PASS or decision.sizing is None:
            raise AtlasError("cannot open a position from a vetoed decision")
        spec = self.loaded.instruments.get(cand.instrument_symbol)
        assert spec is not None
        pos = Position(
            position_id=position_id or f"SIM-{cand.candidate_id}",
            symbol=spec.symbol,
            underlying=spec.underlying,
            direction=cand.direction,
            quantity=decision.sizing.quantity,
            multiplier=spec.multiplier,
            entry=cand.entry,
            stop=cand.stop,
            risk_amount=decision.sizing.planned_risk,
            capital_outlay=decision.sizing.capital_outlay,
            provenance=Provenance.SYNTHETIC,
            opened_at=self.now(),
        )
        return self.open_simulated_position(pos)

    def record_simulated_realization(
        self,
        trade_id: str,
        gross_pnl: Decimal | str,
        costs: Decimal | str,
        position_id: str | None = None,
    ) -> StoredEvent:
        self._require_initialized()
        self._require_simulation()
        if position_id is not None and position_id not in self.state.open_positions:
            raise AtlasError(f"unknown position {position_id}")
        share = self.cfg.profit_allocation.reserve_share
        try:
            alloc = allocate(to_dec(gross_pnl), to_dec(costs), share)
        except LedgerError as exc:
            raise AtlasError(str(exc)) from exc
        payload = {"trade_id": trade_id, "reserve_share": str(share), "simulated": True, **alloc.as_payload()}
        if position_id is not None:
            payload["position_id"] = position_id
        ev = self._append(
            NewEvent(EventType.TRADE_REALIZED, payload, idempotency_key=f"realized:{trade_id}")
        ).event
        self._snapshot()
        return ev

    def close_simulated_position(
        self, position_id: str, exit_price: Decimal | str, costs: Decimal | str
    ) -> StoredEvent:
        pos = self.state.open_positions.get(position_id)
        if pos is None:
            raise AtlasError(f"unknown position {position_id}")
        sign = 1 if pos.direction is Direction.LONG else -1
        gross = (to_dec(exit_price) - pos.entry) * pos.quantity * pos.multiplier * sign
        return self.record_simulated_realization(f"T-{position_id}", gross, costs, position_id)
