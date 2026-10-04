"""Shared test helpers (importable as `helpers`)."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from atlas.domain.enums import Direction, Provenance, TradeType
from atlas.domain.schemas import MarketDataRef, Position, TradeCandidate
from atlas.runtime.clock import IST, FixedClock

REPO_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 5, 10, 0, tzinfo=IST)  # a Monday, 10:00 IST

def make_root(tmp_path: Path, edits: dict[str, list[tuple[str, str]]] | None = None) -> Path:
    """Copy config/ + examples/ into an isolated root, applying (old, new) text edits."""
    root = tmp_path / "root"
    shutil.copytree(REPO_ROOT / "config", root / "config")
    shutil.copytree(REPO_ROOT / "examples", root / "examples")
    for rel, pairs in (edits or {}).items():
        p = root / rel
        text = p.read_text(encoding="utf-8")
        for old, new in pairs:
            assert old in text, f"edit target not found in {rel}: {old!r}"
            text = text.replace(old, new, 1)
        p.write_text(text, encoding="utf-8")
    return root


_counter = {"n": 0}


def cand(clock: FixedClock, **overrides: Any) -> TradeCandidate:
    """A valid SYNTHETIC long cash-equity candidate unless overridden."""
    _counter["n"] += 1
    now = clock.now_utc()
    md = overrides.pop("market_data", None) or MarketDataRef(
        snapshot_id=f"syn-{_counter['n']}",
        source="test",
        provenance=overrides.pop("provenance", Provenance.SYNTHETIC),
        as_of=overrides.pop("as_of", now),
    )
    base: dict[str, Any] = dict(
        candidate_id=f"C{_counter['n']}",
        created_at=now,
        instrument_symbol="SYNTH-EQ",
        direction=Direction.LONG,
        trade_type=TradeType.INTRADAY,
        entry=Decimal("120"),
        stop=Decimal("117.5"),
        targets=(Decimal("125"),),
        est_slippage_per_unit=Decimal("0.05"),
        est_fixed_costs=Decimal("15"),
        market_data=md,
    )
    base.update(overrides)
    return TradeCandidate(**base)


def sim_position(
    pid: str,
    underlying: str = "NIFTY",
    risk: str = "50",
    outlay: str = "500",
    direction: Direction = Direction.LONG,
    symbol: str = "SYNTH-NIFTY-CE",
) -> Position:
    return Position(
        position_id=pid,
        symbol=symbol,
        underlying=underlying,
        direction=direction,
        quantity=1,
        multiplier=Decimal("1"),
        entry=Decimal("100"),
        stop=Decimal("50"),
        risk_amount=Decimal(risk),
        capital_outlay=Decimal(outlay),
        provenance=Provenance.SYNTHETIC,
        opened_at=T0,
    )


def minutes(n: int) -> timedelta:
    return timedelta(minutes=n)
