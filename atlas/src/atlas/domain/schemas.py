"""Typed data contracts shared across engines.

Models are immutable. Monetary/price fields refuse floats (see ``money.to_dec``):
JSON inputs must be parsed with ``parse_float=Decimal`` or use strings.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from atlas.domain.enums import (
    Direction,
    InstrumentKind,
    Provenance,
    RiskMode,
    RiskVerdict,
    TradeType,
    VetoCode,
)
from atlas.domain.money import to_dec

Dec = Annotated[Decimal, BeforeValidator(to_dec)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value


class InstrumentSpec(_Frozen):
    """Exchange contract specification. Must be verified before non-synthetic use."""

    symbol: str
    exchange: str
    kind: InstrumentKind
    underlying: str
    lot_size: int = Field(ge=0)
    multiplier: Dec = Decimal("1")
    tick_size: Dec = Decimal("0")
    verified: bool = False
    provenance: Provenance = Provenance.UNKNOWN
    source: str = ""
    verified_on: str = ""


class MarketDataRef(_Frozen):
    """Pointer to the market-data snapshot a candidate was built from."""

    snapshot_id: str
    source: str
    provenance: Provenance
    as_of: datetime

    _aware = field_validator("as_of")(_require_aware)


class TradeCandidate(_Frozen):
    """A proposed trade before sizing. Phase 1 candidates are SYNTHETIC only."""

    candidate_id: str = Field(min_length=1)
    created_at: datetime
    instrument_symbol: str
    direction: Direction
    trade_type: TradeType
    entry: Dec
    stop: Dec
    targets: tuple[Dec, ...] = Field(min_length=1)
    est_slippage_per_unit: Dec = Decimal("0")
    est_fixed_costs: Dec = Decimal("0")
    margin_per_lot: Dec | None = None
    market_data: MarketDataRef
    strategy: str = "UNSPECIFIED"
    thesis: str = ""
    invalidation: str = ""

    _aware = field_validator("created_at")(_require_aware)


class VetoReason(_Frozen):
    code: VetoCode
    detail: str


class SizingResult(_Frozen):
    risk_budget: Dec  # the budget actually applied (after mode/daily/correlation)
    risk_per_unit: Dec  # stop distance × multiplier + slippage
    max_quantity_by_risk: int
    quantity_cap_by_capital: int | None
    lots: int
    quantity: int
    planned_risk: Dec  # quantity × risk_per_unit + fixed costs
    capital_outlay: Dec  # cash/premium paid or margin blocked
    worst_case_loss: Dec | None  # gap-to-zero for long premium; None if unbounded/unknown
    binding_constraint: str


class BudgetBreakdown(_Frozen):
    trading_capital: Dec
    base_risk_pct: Dec
    mode_multiplier: Dec
    effective_risk_pct: Dec
    per_trade_budget: Dec
    daily_loss_ceiling: Dec
    daily_loss_used: Dec
    open_risk: Dec
    daily_headroom: Dec
    cluster: str | None
    cluster_open_risk: Dec
    cluster_headroom: Dec | None
    applied_budget: Dec


class RiskDecision(_Frozen):
    decision_id: str
    candidate_id: str
    evaluated_at: datetime
    verdict: RiskVerdict
    reasons: tuple[VetoReason, ...] = ()
    sizing: SizingResult | None = None
    budget: BudgetBreakdown | None = None
    risk_mode: RiskMode
    synthetic: bool
    executable: bool  # Phase 1: always False (no execution adapter exists)
    requires_user_approval: bool = True
    risk_engine_version: str
    notes: tuple[str, ...] = ()

    @property
    def vetoed(self) -> bool:
        return self.verdict is RiskVerdict.VETO

    def codes(self) -> set[VetoCode]:
        return {r.code for r in self.reasons}


class Position(_Frozen):
    position_id: str
    symbol: str
    underlying: str
    direction: Direction
    quantity: int = Field(gt=0)
    multiplier: Dec
    entry: Dec
    stop: Dec
    risk_amount: Dec
    capital_outlay: Dec
    provenance: Provenance
    opened_at: datetime


def model_to_payload(model: BaseModel) -> dict[str, Any]:
    """JSON-safe dict (Decimals → str, datetimes → ISO)."""
    return model.model_dump(mode="json")
