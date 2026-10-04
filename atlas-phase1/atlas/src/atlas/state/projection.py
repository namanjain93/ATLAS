"""Deterministic projection of the event log into live state.

State is never mutated directly — only by replaying events. Anomalies found while
replaying (impossible P&L, unknown position, ledger errors) are collected in
``errors`` and cause a HALT at recovery.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from atlas.domain.money import ZERO, paise, to_dec
from atlas.domain.schemas import Position
from atlas.events.model import EventType, StoredEvent
from atlas.ledger.capital import LedgerError, LedgerState, allocate
from atlas.runtime.clock import trading_day

_CAPITAL_EVENTS = {
    EventType.DEPOSIT,
    EventType.WITHDRAWAL,
    EventType.TRADE_REALIZED,
}


@dataclass
class AtlasState:
    tz_offset_minutes: int = 330
    ledger: LedgerState = field(default_factory=LedgerState)
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    realized_by_day: dict[str, Decimal] = field(default_factory=dict)
    day_open_capital: dict[str, Decimal] = field(default_factory=dict)
    open_positions: dict[str, Position] = field(default_factory=dict)
    closed_positions: int = 0
    kill_switch: bool = False
    kill_reason: str = ""
    approved_config: dict[str, str] | None = None
    candidates: set[str] = field(default_factory=set)
    decisions: dict[str, int] = field(default_factory=lambda: {"RISK_PASS": 0, "VETO": 0})
    last_seq: int = 0
    last_hash: str = ""
    errors: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ replay
    def apply(self, ev: StoredEvent) -> None:
        p = ev.payload
        day = trading_day(datetime.fromisoformat(ev.ts_utc), self.tz_offset_minutes).isoformat()
        if ev.type in _CAPITAL_EVENTS and self.ledger.initialized:
            self.day_open_capital.setdefault(day, self.ledger.trading_capital)
        try:
            self._apply(ev, p, day)
        except (LedgerError, ValidationError, KeyError, ValueError, TypeError) as exc:
            self.errors.append(f"seq {ev.seq} {ev.type.value}: {exc}")
        self.last_seq = ev.seq
        self.last_hash = ev.hash

    def _apply(self, ev: StoredEvent, p: dict[str, Any], day: str) -> None:
        t = ev.type
        if t is EventType.CONFIG_APPROVED:
            self.approved_config = {
                "config_version": p["config_version"],
                "constitution_version": p["constitution_version"],
                "fingerprint": p["fingerprint"],
            }
        elif t is EventType.LEDGER_INITIALIZED:
            self.ledger.initialize(to_dec(p["initial_capital"]))
            self.day_open_capital.setdefault(day, self.ledger.trading_capital)
        elif t is EventType.DEPOSIT:
            self.ledger.deposit(to_dec(p["amount"]))
        elif t is EventType.WITHDRAWAL:
            self.ledger.withdraw(to_dec(p["amount"]), p["source"])
        elif t is EventType.TRADE_REALIZED:
            alloc = allocate(to_dec(p["gross_pnl"]), to_dec(p["costs"]), to_dec(p["reserve_share"]))
            for k, v in alloc.as_payload().items():
                if to_dec(p[k]) != to_dec(v):
                    raise ValueError(f"impossible P&L: recorded {k}={p[k]} but recomputed {v}")
            pid = p.get("position_id")
            if pid is not None:
                if pid not in self.open_positions:
                    raise ValueError(f"realization for unknown position {pid}")
                del self.open_positions[pid]
                self.closed_positions += 1
            self.ledger.realize(alloc)
            self.realized_by_day[day] = self.realized_by_day.get(day, ZERO) + alloc.net_pnl
            if alloc.net_pnl < 0:
                self.consecutive_losses += 1
                self.consecutive_wins = 0
            elif alloc.net_pnl > 0:
                self.consecutive_wins += 1
                self.consecutive_losses = 0
        elif t is EventType.POSITION_OPENED:
            pos = Position.model_validate(p["position"])
            if pos.position_id in self.open_positions:
                raise ValueError(f"duplicate open position {pos.position_id}")
            self.open_positions[pos.position_id] = pos
        elif t is EventType.KILL_SWITCH_SET:
            self.kill_switch = bool(p["active"])
            self.kill_reason = p.get("reason", "")
        elif t is EventType.CANDIDATE_RECEIVED:
            self.candidates.add(p["candidate_id"])
        elif t is EventType.RISK_DECISION:
            v = p["verdict"]
            self.decisions[v] = self.decisions.get(v, 0) + 1

    # ------------------------------------------------------------------ queries
    def day_open(self, day: str) -> Decimal:
        return self.day_open_capital.get(day, self.ledger.trading_capital)

    def realized_on(self, day: str) -> Decimal:
        return self.realized_by_day.get(day, ZERO)

    def integrity_errors(self) -> list[str]:
        return list(self.errors) + self.ledger.invariant_errors()

    def to_dict(self) -> dict[str, Any]:
        """Deterministic, JSON-safe view used for snapshots and comparison."""
        return {
            "ledger": self.ledger.to_dict(),
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "realized_by_day": {k: str(paise(v)) for k, v in sorted(self.realized_by_day.items())},
            "day_open_capital": {k: str(paise(v)) for k, v in sorted(self.day_open_capital.items())},
            "open_positions": {
                k: v.model_dump(mode="json") for k, v in sorted(self.open_positions.items())
            },
            "closed_positions": self.closed_positions,
            "kill_switch": self.kill_switch,
            "kill_reason": self.kill_reason,
            "approved_config": self.approved_config,
            "candidates_seen": len(self.candidates),
            "decisions": dict(sorted(self.decisions.items())),
            "last_seq": self.last_seq,
            "last_hash": self.last_hash,
            "errors": list(self.errors),
        }


def replay(events: Iterable[StoredEvent], tz_offset_minutes: int = 330) -> AtlasState:
    st = AtlasState(tz_offset_minutes=tz_offset_minutes)
    for ev in events:
        st.apply(ev)
    return st
