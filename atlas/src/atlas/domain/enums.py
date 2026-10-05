from __future__ import annotations

from enum import Enum


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def sign(self) -> int:
        return 1 if self is Direction.LONG else -1


class TradeType(str, Enum):
    INTRADAY = "INTRADAY"
    SHORT_SWING = "SHORT_SWING"  # 2–5 trading days
    SWING = "SWING"  # 1–4 weeks


class InstrumentKind(str, Enum):
    CASH_EQUITY = "CASH_EQUITY"
    FUTURE = "FUTURE"
    LONG_OPTION = "LONG_OPTION"
    DEBIT_SPREAD = "DEBIT_SPREAD"


class Provenance(str, Enum):
    """Where a piece of market/instrument data came from."""

    LIVE_VERIFIED = "LIVE_VERIFIED"
    DELAYED = "DELAYED"
    EOD = "EOD"
    SYNTHETIC = "SYNTHETIC"  # test/demo data — never executable
    UNKNOWN = "UNKNOWN"


class RuntimeMode(str, Enum):
    SIMULATION = "SIMULATION"  # synthetic data permitted, nothing executable
    PAPER = "PAPER"  # real data required, paper execution only (Phase 5+)


class RuntimeState(str, Enum):
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    READY = "READY"
    SCANNING = "SCANNING"
    ANALYZING = "ANALYZING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    IN_POSITION = "IN_POSITION"
    DEFENSIVE = "DEFENSIVE"
    HALTED = "HALTED"
    ERROR = "ERROR"


class RiskMode(str, Enum):
    NORMAL = "NORMAL"
    REDUCED = "REDUCED"
    DEFENSIVE = "DEFENSIVE"
    VERY_DEFENSIVE = "VERY_DEFENSIVE"
    PAUSED = "PAUSED"

    @property
    def severity(self) -> int:
        return _SEVERITY[self]


_SEVERITY = {
    RiskMode.NORMAL: 0,
    RiskMode.REDUCED: 1,
    RiskMode.DEFENSIVE: 2,
    RiskMode.VERY_DEFENSIVE: 3,
    RiskMode.PAUSED: 4,
}


class RiskVerdict(str, Enum):
    RISK_PASS = "RISK_PASS"  # sized and within limits — NOT a trade authorization
    VETO = "VETO"


class VetoCode(str, Enum):
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    SYSTEM_NOT_READY = "SYSTEM_NOT_READY"
    RISK_MODE_PAUSED = "RISK_MODE_PAUSED"
    INVALID_STRUCTURE = "INVALID_STRUCTURE"
    SHORT_NOT_PERMITTED = "SHORT_NOT_PERMITTED"
    DATA_PROVENANCE_UNKNOWN = "DATA_PROVENANCE_UNKNOWN"
    DATA_UNVERIFIED = "DATA_UNVERIFIED"
    SYNTHETIC_DATA_NOT_ALLOWED = "SYNTHETIC_DATA_NOT_ALLOWED"
    STALE_DATA = "STALE_DATA"
    DATA_TIMESTAMP_IN_FUTURE = "DATA_TIMESTAMP_IN_FUTURE"
    DATA_GRANULARITY_INSUFFICIENT = "DATA_GRANULARITY_INSUFFICIENT"
    INSTRUMENT_UNKNOWN = "INSTRUMENT_UNKNOWN"
    INSTRUMENT_UNVERIFIED = "INSTRUMENT_UNVERIFIED"
    INSTRUMENT_KIND_MISMATCH = "INSTRUMENT_KIND_MISMATCH"
    MARGIN_UNKNOWN = "MARGIN_UNKNOWN"
    MIN_LOT_EXCEEDS_RISK_BUDGET = "MIN_LOT_EXCEEDS_RISK_BUDGET"
    WORST_CASE_LOSS_EXCEEDS_BUDGET = "WORST_CASE_LOSS_EXCEEDS_BUDGET"
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"
    COSTS_EXCEED_BUDGET = "COSTS_EXCEED_BUDGET"
    DAILY_LOSS_CEILING = "DAILY_LOSS_CEILING"
    MAX_POSITIONS = "MAX_POSITIONS"
    CORRELATION_BUDGET_EXHAUSTED = "CORRELATION_BUDGET_EXHAUSTED"
    DUPLICATE_CANDIDATE = "DUPLICATE_CANDIDATE"
