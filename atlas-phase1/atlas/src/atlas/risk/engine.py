"""Deterministic Risk Engine — veto authority over every candidate.

Every gate is evaluated and every failure is recorded (no short-circuit hiding).
Sizing always rounds DOWN. A ``RISK_PASS`` means "sized and within limits"; it is
not an authorization to trade — user approval and a verified execution adapter are
still required, and Phase 1 has no execution adapter at all.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from atlas.config.loader import InstrumentRegistry
from atlas.config.models import AtlasConfig
from atlas.domain.enums import (
    Direction,
    InstrumentKind,
    Provenance,
    RiskMode,
    RiskVerdict,
    RuntimeState,
    TradeType,
    VetoCode,
)
from atlas.domain.money import ZERO, floor_int
from atlas.domain.schemas import (
    BudgetBreakdown,
    InstrumentSpec,
    MarketDataRef,
    RiskDecision,
    SizingResult,
    TradeCandidate,
    VetoReason,
)
from atlas.risk.state import RiskState
from atlas.version import RISK_ENGINE_VERSION

_OPERATIONAL_STATES = {
    RuntimeState.READY,
    RuntimeState.SCANNING,
    RuntimeState.ANALYZING,
    RuntimeState.IN_POSITION,
    RuntimeState.DEFENSIVE,
}


class SnapshotVerifier(Protocol):
    """Confirms a non-synthetic market-data snapshot exists in a verified data store."""

    def verify(self, ref: MarketDataRef) -> bool: ...


class NoVerifiedDataSource:
    """Phase 1 default: no market-data adapter exists, so nothing real can be verified."""

    def verify(self, ref: MarketDataRef) -> bool:  # noqa: ARG002
        return False


class RiskEngineInvariantError(AssertionError):
    """Raised if sizing ever produces risk above budget — a bug, never a trade."""


@dataclass
class _Ctx:
    reasons: list[VetoReason]
    notes: list[str]

    def veto(self, code: VetoCode, detail: str) -> None:
        self.reasons.append(VetoReason(code=code, detail=detail))


class RiskEngine:
    def __init__(
        self,
        config: AtlasConfig,
        instruments: InstrumentRegistry,
        verifier: SnapshotVerifier | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.cfg = config
        self.instruments = instruments
        self.verifier = verifier or NoVerifiedDataSource()
        self._new_id = id_factory or (lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------ public
    def cluster_key(self, underlying: str) -> str:
        return self.cfg.risk.correlation.cluster_of(underlying) or f"UNDERLYING:{underlying}"

    def evaluate(
        self,
        cand: TradeCandidate,
        rs: RiskState,
        runtime_state: RuntimeState,
        now: datetime,
    ) -> RiskDecision:
        ctx = _Ctx(reasons=[], notes=[])
        spec = self.instruments.get(cand.instrument_symbol)

        self._system_gates(rs, runtime_state, ctx)
        structure_ok = self._structure_gates(cand, spec, ctx)
        self._data_gates(cand, spec, now, ctx)
        instrument_ok = self._instrument_gates(cand, spec, ctx)
        budget = self._budget(rs, spec, ctx)
        self._portfolio_gates(rs, budget, ctx)

        sizing: SizingResult | None = None
        if structure_ok and instrument_ok and spec is not None and budget.applied_budget > 0:
            sizing = self._size(cand, spec, rs, budget, ctx)

        synthetic = cand.market_data.provenance is Provenance.SYNTHETIC or (
            spec is not None and spec.provenance is Provenance.SYNTHETIC
        )
        if synthetic:
            ctx.notes.append("SYNTHETIC candidate: never executable")
        if rs.consecutive_wins >= 3:
            ctx.notes.append(f"{rs.consecutive_wins} consecutive wins: risk NOT increased (by design)")
        if rs.mode_reasons:
            ctx.notes.extend(rs.mode_reasons)
        verdict = RiskVerdict.VETO if ctx.reasons else RiskVerdict.RISK_PASS
        if verdict is RiskVerdict.RISK_PASS:
            ctx.notes.append("RISK_PASS is not a trade authorization: user approval required")
        return RiskDecision(
            decision_id=self._new_id(),
            candidate_id=cand.candidate_id,
            evaluated_at=now,
            verdict=verdict,
            reasons=tuple(ctx.reasons),
            sizing=sizing,
            budget=budget,
            risk_mode=rs.mode,
            synthetic=synthetic,
            executable=False,  # Phase 1: no execution adapter exists
            requires_user_approval=True,
            risk_engine_version=RISK_ENGINE_VERSION,
            notes=tuple(ctx.notes),
        )

    # ------------------------------------------------------------------ gates
    def _system_gates(self, rs: RiskState, runtime_state: RuntimeState, ctx: _Ctx) -> None:
        if rs.kill_switch:
            ctx.veto(VetoCode.KILL_SWITCH_ACTIVE, "kill switch is active")
        if runtime_state not in _OPERATIONAL_STATES:
            ctx.veto(VetoCode.SYSTEM_NOT_READY, f"runtime state is {runtime_state.value}")
        if rs.mode is RiskMode.PAUSED:
            ctx.veto(VetoCode.RISK_MODE_PAUSED, "; ".join(rs.mode_reasons) or "risk mode PAUSED")

    def _structure_gates(self, c: TradeCandidate, spec: InstrumentSpec | None, ctx: _Ctx) -> bool:
        ok = True

        def bad(detail: str) -> None:
            nonlocal ok
            ok = False
            ctx.veto(VetoCode.INVALID_STRUCTURE, detail)

        if c.entry <= 0:
            bad("entry must be positive")
        if c.stop < 0:
            bad("stop cannot be negative")
        if c.est_slippage_per_unit < 0 or c.est_fixed_costs < 0:
            bad("cost estimates cannot be negative")
        if c.direction is Direction.LONG:
            if not c.stop < c.entry:
                bad(f"LONG stop {c.stop} must be below entry {c.entry}")
            if any(t <= c.entry for t in c.targets):
                bad("LONG targets must be above entry")
        else:
            if not c.stop > c.entry:
                bad(f"SHORT stop {c.stop} must be above entry {c.entry}")
            if any(t >= c.entry for t in c.targets):
                bad("SHORT targets must be below entry")
        if spec is not None:
            if spec.kind in (InstrumentKind.LONG_OPTION, InstrumentKind.DEBIT_SPREAD):
                if c.direction is not Direction.LONG:
                    ok = False
                    ctx.veto(
                        VetoCode.INSTRUMENT_KIND_MISMATCH,
                        f"{spec.kind.value} is bought premium; express bearish views with puts, "
                        "not by shorting premium",
                    )
            if (
                spec.kind is InstrumentKind.CASH_EQUITY
                and c.direction is Direction.SHORT
                and c.trade_type is not TradeType.INTRADAY
            ):
                ok = False
                ctx.veto(VetoCode.SHORT_NOT_PERMITTED, "cash-equity shorts must be intraday")
        return ok

    def _data_gates(
        self, c: TradeCandidate, spec: InstrumentSpec | None, now: datetime, ctx: _Ctx
    ) -> None:
        md = c.market_data
        dcfg = self.cfg.data
        if md.provenance is Provenance.UNKNOWN:
            ctx.veto(VetoCode.DATA_PROVENANCE_UNKNOWN, "market-data provenance is UNKNOWN")
        elif md.provenance is Provenance.SYNTHETIC:
            if not self.cfg.synthetic_allowed:
                ctx.veto(
                    VetoCode.SYNTHETIC_DATA_NOT_ALLOWED,
                    f"synthetic data refused in {self.cfg.runtime.mode.value} mode",
                )
        else:
            if spec is not None and spec.provenance is Provenance.SYNTHETIC:
                ctx.veto(VetoCode.DATA_UNVERIFIED, "real data paired with a synthetic instrument")
            if not self.verifier.verify(md):
                ctx.veto(
                    VetoCode.DATA_UNVERIFIED,
                    f"snapshot {md.snapshot_id!r} from {md.source!r} cannot be verified "
                    "(no verified market-data source)",
                )
            if c.trade_type is TradeType.INTRADAY and md.provenance is not Provenance.LIVE_VERIFIED:
                ctx.veto(
                    VetoCode.DATA_GRANULARITY_INSUFFICIENT,
                    f"intraday decisions require LIVE_VERIFIED data, got {md.provenance.value}",
                )
        age = (now - md.as_of).total_seconds()
        if age < -dcfg.max_future_skew_seconds:
            ctx.veto(VetoCode.DATA_TIMESTAMP_IN_FUTURE, f"data timestamp {-age:.0f}s in the future")
        max_age = (
            dcfg.max_age_seconds_intraday
            if c.trade_type is TradeType.INTRADAY
            else dcfg.max_age_seconds_swing
        )
        if age > max_age:
            ctx.veto(VetoCode.STALE_DATA, f"data age {age:.0f}s exceeds {max_age}s")

    def _instrument_gates(self, c: TradeCandidate, spec: InstrumentSpec | None, ctx: _Ctx) -> bool:
        if spec is None:
            ctx.veto(VetoCode.INSTRUMENT_UNKNOWN, f"no instrument spec for {c.instrument_symbol}")
            return False
        if not spec.verified or spec.lot_size <= 0 or spec.multiplier <= 0:
            ctx.veto(
                VetoCode.INSTRUMENT_UNVERIFIED,
                f"{spec.symbol}: contract spec unverified (lot_size={spec.lot_size}); "
                "fill from the current exchange circular",
            )
            return False
        if spec.kind is InstrumentKind.FUTURE and (c.margin_per_lot is None or c.margin_per_lot <= 0):
            ctx.veto(VetoCode.MARGIN_UNKNOWN, "futures require a verified margin_per_lot")
            return False
        return True

    def _budget(self, rs: RiskState, spec: InstrumentSpec | None, ctx: _Ctx) -> BudgetBreakdown:
        per_trade = rs.per_trade_budget
        cluster = self.cluster_key(spec.underlying) if spec else None
        cluster_open = ZERO
        cluster_headroom: Decimal | None = None
        if cluster is not None:
            same = [p for p in rs.open_positions if self.cluster_key(p.underlying) == cluster]
            cluster_open = sum((p.risk_amount for p in same), ZERO)
            if same:
                cap = per_trade * self.cfg.risk.correlation.cluster_risk_multiple
                cluster_headroom = cap - cluster_open
                ctx.notes.append(
                    f"correlated with open position(s) in {cluster}: shared budget {cap:.2f}, "
                    f"used {cluster_open:.2f}"
                )
        candidates = [per_trade, rs.daily_headroom]
        if cluster_headroom is not None:
            candidates.append(cluster_headroom)
        applied = max(ZERO, min(candidates))
        return BudgetBreakdown(
            trading_capital=rs.trading_capital,
            base_risk_pct=rs.base_risk_pct,
            mode_multiplier=rs.mode_multiplier,
            effective_risk_pct=rs.effective_risk_pct,
            per_trade_budget=per_trade,
            daily_loss_ceiling=rs.daily_loss_ceiling,
            daily_loss_used=rs.daily_loss_used,
            open_risk=rs.open_risk,
            daily_headroom=rs.daily_headroom,
            cluster=cluster,
            cluster_open_risk=cluster_open,
            cluster_headroom=cluster_headroom,
            applied_budget=applied,
        )

    def _portfolio_gates(self, rs: RiskState, b: BudgetBreakdown, ctx: _Ctx) -> None:
        maxp = self.cfg.risk.max_concurrent_positions
        if len(rs.open_positions) >= maxp:
            ctx.veto(VetoCode.MAX_POSITIONS, f"{len(rs.open_positions)} open positions (max {maxp})")
        if b.daily_headroom <= 0:
            ctx.veto(
                VetoCode.DAILY_LOSS_CEILING,
                f"daily loss used {b.daily_loss_used:.2f} + open risk {b.open_risk:.2f} "
                f"≥ ceiling {b.daily_loss_ceiling:.2f}",
            )
        if b.cluster_headroom is not None and b.cluster_headroom <= 0:
            ctx.veto(
                VetoCode.CORRELATION_BUDGET_EXHAUSTED,
                f"cluster {b.cluster} already uses its shared risk budget",
            )

    # ------------------------------------------------------------------ sizing
    def _size(
        self,
        c: TradeCandidate,
        spec: InstrumentSpec,
        rs: RiskState,
        b: BudgetBreakdown,
        ctx: _Ctx,
    ) -> SizingResult | None:
        budget = b.applied_budget
        fixed = c.est_fixed_costs
        lot = spec.lot_size
        mult = spec.multiplier
        rpu = (abs(c.entry - c.stop) + c.est_slippage_per_unit) * mult
        if fixed >= budget:
            ctx.veto(VetoCode.COSTS_EXCEED_BUDGET, f"fixed costs {fixed} ≥ risk budget {budget:.2f}")
            return None
        if rpu <= 0:
            ctx.veto(VetoCode.INVALID_STRUCTURE, "risk per unit must be positive")
            return None

        max_qty_risk = floor_int((budget - fixed) / rpu)
        lots_by_risk = max_qty_risk // lot
        caps: dict[str, int] = {"RISK": lots_by_risk}

        available = rs.trading_capital - rs.open_outlay  # reserve is never available
        qty_cap_capital: int | None = None
        if spec.kind is InstrumentKind.FUTURE:
            assert c.margin_per_lot is not None
            caps["CAPITAL"] = floor_int(available / c.margin_per_lot) if available > 0 else 0
            qty_cap_capital = caps["CAPITAL"] * lot
        else:
            unit_outlay = c.entry * mult
            qty_cap_capital = floor_int(available / unit_outlay) if available > 0 else 0
            caps["CAPITAL"] = qty_cap_capital // lot
        if spec.kind in (InstrumentKind.LONG_OPTION, InstrumentKind.DEBIT_SPREAD):
            wc_budget = budget * self.cfg.risk.options.worst_case_loss_multiple - fixed
            caps["WORST_CASE"] = (
                floor_int(wc_budget / (c.entry * mult)) // lot if wc_budget > 0 else 0
            )

        binding = min(caps, key=lambda k: (caps[k], k != "RISK"))
        lots = caps[binding]
        one_lot_risk = lot * rpu + fixed
        if lots_by_risk == 0:
            ctx.veto(
                VetoCode.MIN_LOT_EXCEEDS_RISK_BUDGET,
                f"one lot ({lot} × {rpu:.2f}/unit + costs {fixed}) risks {one_lot_risk:.2f} "
                f"> budget {budget:.2f}; instrument rejected — alternative structure search "
                "required (Instrument Engine, Phase 4); fractional lots are never invented",
            )
        elif lots == 0 and binding == "CAPITAL":
            ctx.veto(VetoCode.INSUFFICIENT_CAPITAL, f"available capital {available:.2f} < one lot outlay")
        elif lots == 0 and binding == "WORST_CASE":
            ctx.veto(
                VetoCode.WORST_CASE_LOSS_EXCEEDS_BUDGET,
                f"one lot premium {lot * c.entry * mult:.2f} + costs {fixed} could be lost on a gap; "
                f"exceeds {budget * self.cfg.risk.options.worst_case_loss_multiple:.2f}",
            )

        qty = lots * lot
        planned = qty * rpu + fixed if qty > 0 else ZERO
        if planned > budget:
            raise RiskEngineInvariantError(f"planned risk {planned} exceeds budget {budget}")
        if spec.kind is InstrumentKind.FUTURE:
            assert c.margin_per_lot is not None
            outlay = lots * c.margin_per_lot
        else:
            outlay = qty * c.entry * mult
        if spec.kind in (InstrumentKind.LONG_OPTION, InstrumentKind.DEBIT_SPREAD):
            worst: Decimal | None = outlay + fixed if qty else ZERO
        elif spec.kind is InstrumentKind.CASH_EQUITY and c.direction is Direction.LONG:
            worst = outlay + fixed if qty else ZERO
        else:
            worst = None  # futures / shorts: gap loss not bounded by structure
        if lots > 0 and binding != "RISK":
            ctx.notes.append(f"size capped by {binding} ({caps[binding]} lots vs {lots_by_risk} by risk)")
        return SizingResult(
            risk_budget=budget,
            risk_per_unit=rpu,
            max_quantity_by_risk=max_qty_risk,
            quantity_cap_by_capital=qty_cap_capital,
            lots=lots,
            quantity=qty,
            planned_risk=planned,
            capital_outlay=outlay,
            worst_case_loss=worst,
            binding_constraint=binding,
        )
