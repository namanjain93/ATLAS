"""Risk state derived (never stored independently) from the projected ledger/portfolio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from atlas.config.models import AtlasConfig
from atlas.domain.enums import RiskMode
from atlas.domain.money import ZERO
from atlas.domain.schemas import Position
from atlas.risk.modes import resolve_mode
from atlas.runtime.clock import trading_day
from atlas.state.projection import AtlasState


@dataclass(frozen=True)
class RiskState:
    as_of: datetime
    trading_day: str
    trading_capital: Decimal
    reserve: Decimal  # informational only — never used for sizing
    peak_trading_capital: Decimal
    drawdown_pct: Decimal
    consecutive_losses: int
    consecutive_wins: int
    day_open_capital: Decimal
    daily_realized_pnl: Decimal
    open_positions: tuple[Position, ...]
    kill_switch: bool
    mode: RiskMode
    mode_reasons: tuple[str, ...]
    mode_multiplier: Decimal
    base_risk_pct: Decimal
    daily_loss_pct: Decimal

    @property
    def effective_risk_pct(self) -> Decimal:
        return self.base_risk_pct * self.mode_multiplier

    @property
    def per_trade_budget(self) -> Decimal:
        return self.trading_capital * self.effective_risk_pct

    @property
    def daily_loss_ceiling(self) -> Decimal:
        return self.day_open_capital * self.daily_loss_pct

    @property
    def daily_loss_used(self) -> Decimal:
        return max(ZERO, -self.daily_realized_pnl)

    @property
    def open_risk(self) -> Decimal:
        return sum((p.risk_amount for p in self.open_positions), ZERO)

    @property
    def open_outlay(self) -> Decimal:
        return sum((p.capital_outlay for p in self.open_positions), ZERO)

    @property
    def daily_headroom(self) -> Decimal:
        return self.daily_loss_ceiling - self.daily_loss_used - self.open_risk


def build_risk_state(state: AtlasState, cfg: AtlasConfig, now: datetime) -> RiskState:
    led = state.ledger
    day = trading_day(now, cfg.runtime.timezone_offset_minutes).isoformat()
    dd = led.drawdown_pct
    mode, reasons = resolve_mode(dd, state.consecutive_losses, cfg.risk)
    return RiskState(
        as_of=now,
        trading_day=day,
        trading_capital=led.trading_capital,
        reserve=led.reserve,
        peak_trading_capital=led.peak_trading_capital,
        drawdown_pct=dd,
        consecutive_losses=state.consecutive_losses,
        consecutive_wins=state.consecutive_wins,
        day_open_capital=state.day_open(day),
        daily_realized_pnl=state.realized_on(day),
        open_positions=tuple(state.open_positions.values()),
        kill_switch=state.kill_switch,
        mode=mode,
        mode_reasons=tuple(reasons),
        mode_multiplier=cfg.risk.mode_multipliers.for_mode(mode),
        base_risk_pct=cfg.risk.risk_per_trade_pct,
        daily_loss_pct=cfg.risk.daily_loss_pct,
    )
