"""Typed configuration + Constitution models.

The Constitution defines hard ceilings. ``AtlasConfig.check_against`` refuses any
operating config that is less conservative than the Constitution. These checks are
code, not prompts: an LLM (or a user typo) cannot raise a risk limit past them.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.domain.enums import RiskMode, RuntimeMode
from atlas.domain.schemas import Dec


class ConfigError(Exception):
    """Configuration is invalid or violates the Constitution."""


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ----------------------------------------------------------------------------- constitution


class ConstitutionMeta(_Strict):
    version: str


class Ceilings(_Strict):
    max_risk_per_trade_pct: Dec
    max_daily_loss_pct: Dec
    max_concurrent_positions: int = Field(ge=1)
    reserve_share_of_net_profit: Dec


class NonNegotiables(_Strict):
    user_approval_required: Literal[True]
    live_execution_allowed: Literal[False]
    size_increase_after_loss_allowed: Literal[False]
    stop_widening_allowed: Literal[False]


class Constitution(_Strict):
    constitution: ConstitutionMeta
    ceilings: Ceilings
    non_negotiables: NonNegotiables

    @property
    def version(self) -> str:
        return self.constitution.version


# ----------------------------------------------------------------------------- operating config


class CapitalCfg(_Strict):
    initial_trading_capital: Dec
    currency: Literal["INR"] = "INR"


class DrawdownCfg(_Strict):
    reduced_at: Dec
    defensive_at: Dec
    very_defensive_at: Dec
    paused_at: Dec

    @model_validator(mode="after")
    def _ordered(self) -> "DrawdownCfg":
        seq = [self.reduced_at, self.defensive_at, self.very_defensive_at, self.paused_at]
        if not all(Decimal(0) < a < b for a, b in zip(seq, seq[1:])) or seq[0] <= 0:
            raise ValueError("drawdown thresholds must be positive and strictly increasing")
        if self.paused_at > Decimal("1"):
            raise ValueError("drawdown thresholds are fractions (≤ 1)")
        return self


class StreakCfg(_Strict):
    reduced_at: int = Field(ge=1)
    defensive_at: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> "StreakCfg":
        if self.defensive_at <= self.reduced_at:
            raise ValueError("losing_streak.defensive_at must exceed reduced_at")
        return self


class ModeMultipliers(_Strict):
    NORMAL: Dec
    REDUCED: Dec
    DEFENSIVE: Dec
    VERY_DEFENSIVE: Dec
    PAUSED: Dec

    def for_mode(self, mode: RiskMode) -> Decimal:
        return getattr(self, mode.value)

    @model_validator(mode="after")
    def _bounded(self) -> "ModeMultipliers":
        vals = [self.NORMAL, self.REDUCED, self.DEFENSIVE, self.VERY_DEFENSIVE, self.PAUSED]
        if any(v < 0 or v > 1 for v in vals):
            raise ValueError("mode multipliers must be within [0, 1] — risk can never be scaled up")
        if any(b > a for a, b in zip(vals, vals[1:])):
            raise ValueError("mode multipliers must be non-increasing with severity")
        if self.PAUSED != 0:
            raise ValueError("PAUSED multiplier must be 0")
        return self


class CorrelationCfg(_Strict):
    cluster_risk_multiple: Dec
    clusters: dict[str, list[str]]

    @model_validator(mode="after")
    def _valid(self) -> "CorrelationCfg":
        if not (Decimal(0) < self.cluster_risk_multiple <= Decimal(1)):
            raise ValueError("cluster_risk_multiple must be in (0, 1]")
        seen: dict[str, str] = {}
        for name, members in self.clusters.items():
            for m in members:
                if m in seen:
                    raise ValueError(f"underlying {m} appears in clusters {seen[m]} and {name}")
                seen[m] = name
        return self

    def cluster_of(self, underlying: str) -> str | None:
        for name, members in self.clusters.items():
            if underlying in members:
                return name
        return None


class OptionsCfg(_Strict):
    worst_case_loss_multiple: Dec

    @model_validator(mode="after")
    def _valid(self) -> "OptionsCfg":
        if not (Decimal(0) < self.worst_case_loss_multiple <= Decimal(1)):
            raise ValueError("options.worst_case_loss_multiple must be in (0, 1]")
        return self


class RiskCfg(_Strict):
    risk_per_trade_pct: Dec
    daily_loss_pct: Dec
    max_concurrent_positions: int = Field(ge=1)
    drawdown: DrawdownCfg
    losing_streak: StreakCfg
    mode_multipliers: ModeMultipliers
    correlation: CorrelationCfg
    options: OptionsCfg


class ProfitAllocationCfg(_Strict):
    reserve_share: Dec


class DataCfg(_Strict):
    max_age_seconds_intraday: int = Field(gt=0)
    max_age_seconds_swing: int = Field(gt=0)
    max_future_skew_seconds: int = Field(ge=0)
    allow_synthetic: bool


class RuntimeCfg(_Strict):
    mode: RuntimeMode
    timezone_offset_minutes: int = 330


class ExecutionCfg(_Strict):
    adapter: Literal["NONE"]  # Phase 1: no execution adapter may be configured
    user_approval_required: Literal[True]


class InstrumentsCfg(_Strict):
    files: list[str]
    synthetic_files: list[str] = []


class AtlasConfig(_Strict):
    config_version: str
    capital: CapitalCfg
    risk: RiskCfg
    profit_allocation: ProfitAllocationCfg
    data: DataCfg
    runtime: RuntimeCfg
    execution: ExecutionCfg
    instruments: InstrumentsCfg

    @property
    def synthetic_allowed(self) -> bool:
        return self.runtime.mode is RuntimeMode.SIMULATION and self.data.allow_synthetic

    def check_against(self, c: Constitution) -> None:
        """Raise ConfigError if this config is less conservative than the Constitution."""
        errors: list[str] = []
        r, ceil = self.risk, c.ceilings
        if not (Decimal(0) < r.risk_per_trade_pct <= ceil.max_risk_per_trade_pct):
            errors.append(
                f"risk_per_trade_pct {r.risk_per_trade_pct} outside (0, {ceil.max_risk_per_trade_pct}]"
            )
        if not (Decimal(0) < r.daily_loss_pct <= ceil.max_daily_loss_pct):
            errors.append(f"daily_loss_pct {r.daily_loss_pct} outside (0, {ceil.max_daily_loss_pct}]")
        if r.max_concurrent_positions > ceil.max_concurrent_positions:
            errors.append(
                f"max_concurrent_positions {r.max_concurrent_positions} > {ceil.max_concurrent_positions}"
            )
        if self.profit_allocation.reserve_share != ceil.reserve_share_of_net_profit:
            errors.append(
                "profit_allocation.reserve_share must equal the Constitution "
                f"({ceil.reserve_share_of_net_profit})"
            )
        if r.mode_multipliers.NORMAL > Decimal(1):
            errors.append("NORMAL multiplier > 1")
        if self.capital.initial_trading_capital <= 0:
            errors.append("initial_trading_capital must be positive")
        if not c.non_negotiables.user_approval_required or not self.execution.user_approval_required:
            errors.append("user approval cannot be disabled")
        if errors:
            raise ConfigError("Config violates Constitution: " + "; ".join(errors))
