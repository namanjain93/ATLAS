"""Adaptive risk modes from drawdown and losing streak.

Modes only ever REDUCE risk. A winning streak never raises the multiplier above NORMAL.
"""

from __future__ import annotations

from decimal import Decimal

from atlas.config.models import RiskCfg
from atlas.domain.enums import RiskMode


def drawdown_mode(drawdown: Decimal, cfg: RiskCfg) -> RiskMode:
    d = cfg.drawdown
    if drawdown > d.paused_at:
        return RiskMode.PAUSED
    if drawdown >= d.very_defensive_at:
        return RiskMode.VERY_DEFENSIVE
    if drawdown >= d.defensive_at:
        return RiskMode.DEFENSIVE
    if drawdown >= d.reduced_at:
        return RiskMode.REDUCED
    return RiskMode.NORMAL


def streak_mode(consecutive_losses: int, cfg: RiskCfg) -> RiskMode:
    s = cfg.losing_streak
    if consecutive_losses >= s.defensive_at:
        return RiskMode.DEFENSIVE
    if consecutive_losses >= s.reduced_at:
        return RiskMode.REDUCED
    return RiskMode.NORMAL


def resolve_mode(drawdown: Decimal, consecutive_losses: int, cfg: RiskCfg) -> tuple[RiskMode, list[str]]:
    """Most restrictive of the drawdown and streak modes, with human-readable reasons."""
    dm = drawdown_mode(drawdown, cfg)
    sm = streak_mode(consecutive_losses, cfg)
    reasons: list[str] = []
    if dm is not RiskMode.NORMAL:
        reasons.append(f"drawdown {(drawdown * 100).quantize(Decimal('0.01'))}% → {dm.value}")
    if sm is not RiskMode.NORMAL:
        reasons.append(f"{consecutive_losses} consecutive losses → {sm.value}")
    mode = dm if dm.severity >= sm.severity else sm
    return mode, reasons
