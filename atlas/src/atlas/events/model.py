"""Immutable audit event model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Priority(str, Enum):
    P0 = "P0"  # emergency
    P1 = "P1"  # critical market event
    P2 = "P2"  # opportunity / decision
    P3 = "P3"  # background / bookkeeping


class EventType(str, Enum):
    # configuration & runtime
    CONFIG_APPROVED = "CONFIG_APPROVED"
    RUNTIME_STARTED = "RUNTIME_STARTED"
    RUNTIME_HALTED = "RUNTIME_HALTED"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    KILL_SWITCH_SET = "KILL_SWITCH_SET"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    # capital ledger
    LEDGER_INITIALIZED = "LEDGER_INITIALIZED"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRADE_REALIZED = "TRADE_REALIZED"
    # decisions
    CANDIDATE_RECEIVED = "CANDIDATE_RECEIVED"
    RISK_DECISION = "RISK_DECISION"
    # positions (Phase 1: simulation fixtures only — no execution venue exists).
    # A position is closed by TRADE_REALIZED carrying its position_id (single atomic event).
    POSITION_OPENED = "POSITION_OPENED"


DEFAULT_PRIORITY: dict[EventType, Priority] = {
    EventType.KILL_SWITCH_SET: Priority.P0,
    EventType.INTEGRITY_FAILURE: Priority.P0,
    EventType.RUNTIME_HALTED: Priority.P0,
    EventType.CANDIDATE_RECEIVED: Priority.P2,
    EventType.RISK_DECISION: Priority.P2,
    EventType.POSITION_OPENED: Priority.P2,
}


@dataclass(frozen=True)
class NewEvent:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    priority: Priority | None = None

    @property
    def effective_priority(self) -> Priority:
        return self.priority or DEFAULT_PRIORITY.get(self.type, Priority.P3)


@dataclass(frozen=True)
class StoredEvent:
    seq: int
    event_id: str
    idempotency_key: str | None
    type: EventType
    priority: Priority
    ts_utc: str
    payload: dict[str, Any]
    config_version: str
    config_hash: str
    atlas_version: str
    prev_hash: str
    hash: str
