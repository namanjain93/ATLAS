"""SYNTHETIC trade candidates for Phase 1 demonstrations and tests.

Every candidate produced here carries ``Provenance.SYNTHETIC`` and refers to a
SYNTHETIC instrument. They are not market data and can never become executable.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from atlas.domain.enums import Direction, Provenance, TradeType
from atlas.domain.schemas import MarketDataRef, TradeCandidate

SCENARIOS = (
    "pass-long-equity",
    "pass-short-equity",
    "futures-min-lot-overflow",
    "option-affordable",
    "cheap-option-trap",
    "stale-data",
    "invalid-stop",
)


def synthetic_candidate(scenario: str, now: datetime, candidate_id: str | None = None) -> TradeCandidate:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {', '.join(SCENARIOS)}")
    cid = candidate_id or f"SYN-{scenario}-{now.strftime('%Y%m%dT%H%M%S')}"
    md_time = now - timedelta(days=3) if scenario == "stale-data" else now
    base: dict[str, Any] = {
        "candidate_id": cid,
        "created_at": now,
        "trade_type": TradeType.INTRADAY,
        "market_data": MarketDataRef(
            snapshot_id=f"synthetic-{cid}",
            source="atlas.synthetic",
            provenance=Provenance.SYNTHETIC,
            as_of=md_time,
        ),
        "strategy": "SYNTHETIC_FIXTURE",
        "thesis": "Synthetic fixture for Phase 1 Risk Engine demonstration — not a market view.",
    }
    D = Decimal
    if scenario in ("pass-long-equity", "stale-data"):
        spec = dict(instrument_symbol="SYNTH-EQ", direction=Direction.LONG, entry=D("120.00"),
                    stop=D("117.50"), targets=(D("124.00"), D("126.00")),
                    est_slippage_per_unit=D("0.05"), est_fixed_costs=D("15.00"),
                    invalidation="15m close below 117.50")
    elif scenario == "pass-short-equity":
        spec = dict(instrument_symbol="SYNTH-EQ", direction=Direction.SHORT, entry=D("120.00"),
                    stop=D("122.50"), targets=(D("116.00"),), est_slippage_per_unit=D("0.05"),
                    est_fixed_costs=D("15.00"), invalidation="15m close above 122.50")
    elif scenario == "futures-min-lot-overflow":
        spec = dict(instrument_symbol="SYNTH-NIFTY-FUT", direction=Direction.LONG,
                    entry=D("25000.00"), stop=D("24960.00"), targets=(D("25080.00"),),
                    est_slippage_per_unit=D("1.00"), est_fixed_costs=D("60.00"),
                    margin_per_lot=D("150000.00"), invalidation="5m close below 24960")
    elif scenario == "option-affordable":
        spec = dict(instrument_symbol="SYNTH-BANKNIFTY-PE", direction=Direction.LONG,
                    entry=D("40.00"), stop=D("28.00"), targets=(D("64.00"),),
                    est_slippage_per_unit=D("0.50"), est_fixed_costs=D("25.00"),
                    invalidation="underlying reclaims prior swing high")
    elif scenario == "cheap-option-trap":
        spec = dict(instrument_symbol="SYNTH-NIFTY-CE", direction=Direction.LONG,
                    entry=D("3.00"), stop=D("1.50"), targets=(D("9.00"),),
                    est_slippage_per_unit=D("0.30"), est_fixed_costs=D("40.00"),
                    invalidation="far OTM lottery ticket")
    else:  # invalid-stop
        spec = dict(instrument_symbol="SYNTH-EQ", direction=Direction.LONG, entry=D("120.00"),
                    stop=D("121.00"), targets=(D("124.00"),), invalidation="n/a")
    return TradeCandidate(**base, **spec)
