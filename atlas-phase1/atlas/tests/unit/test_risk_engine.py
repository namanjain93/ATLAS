from datetime import timedelta
from decimal import Decimal

import pytest
from helpers import cand, make_root

from atlas.domain.enums import Direction, Provenance, RiskVerdict, TradeType, VetoCode
from atlas.domain.money import floor_int
from atlas.runtime.service import Atlas

D = Decimal


def test_sizing_formula_exact(atlas, clock):
    d, _ = atlas.evaluate(cand(clock))
    s = d.sizing
    # max_risk = 5000 × 2% = 100; rpu = (120−117.5 + 0.05) × 1 = 2.55; (100 − 15)/2.55 = 33.33 → 33
    assert d.verdict is RiskVerdict.RISK_PASS
    assert d.budget.per_trade_budget == D("100")
    assert s.risk_per_unit == D("2.55")
    assert s.quantity == 33
    assert s.planned_risk == D("33") * D("2.55") + D("15")
    assert s.planned_risk <= d.budget.applied_budget


def test_sizing_never_rounds_up_across_grid(atlas, clock):
    for i, stop in enumerate([D("119.99"), D("119.5"), D("118.37"), D("115"), D("100.01"), D("60")]):
        d, _ = atlas.evaluate(cand(clock, stop=stop, est_fixed_costs=D("0"), est_slippage_per_unit=D("0")))
        if d.sizing and d.sizing.quantity:
            rpu = D("120") - stop
            assert d.sizing.quantity == min(floor_int(D("100") / rpu), floor_int(D("5000") / D("120")))
            assert d.sizing.planned_risk <= D("100")


def test_kill_switch_vetoes(atlas, clock):
    atlas.set_kill_switch(True, "test")
    d, _ = atlas.evaluate(cand(clock))
    assert VetoCode.KILL_SWITCH_ACTIVE in d.codes()
    assert VetoCode.SYSTEM_NOT_READY in d.codes()


@pytest.mark.parametrize(
    "overrides",
    [
        dict(stop=D("121")),  # long stop above entry
        dict(direction=Direction.SHORT, stop=D("119"), targets=(D("115"),)),
        dict(targets=(D("110"),)),  # long target below entry
    ],
)
def test_invalid_structure_vetoed(atlas, clock, overrides):
    d, _ = atlas.evaluate(cand(clock, **overrides))
    assert VetoCode.INVALID_STRUCTURE in d.codes()


def test_cash_short_must_be_intraday(atlas, clock):
    d, _ = atlas.evaluate(
        cand(clock, direction=Direction.SHORT, stop=D("122.5"), targets=(D("115"),), trade_type=TradeType.SWING)
    )
    assert VetoCode.SHORT_NOT_PERMITTED in d.codes()


def test_unknown_provenance_vetoed(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, provenance=Provenance.UNKNOWN))
    assert VetoCode.DATA_PROVENANCE_UNKNOWN in d.codes()


def test_claimed_live_data_is_not_trusted_without_verified_source(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, provenance=Provenance.LIVE_VERIFIED))
    assert VetoCode.DATA_UNVERIFIED in d.codes()


def test_eod_data_insufficient_for_intraday(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, provenance=Provenance.EOD))
    assert VetoCode.DATA_GRANULARITY_INSUFFICIENT in d.codes()


def test_future_timestamp_vetoed(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, as_of=clock.now_utc() + timedelta(minutes=5)))
    assert VetoCode.DATA_TIMESTAMP_IN_FUTURE in d.codes()


def test_unverified_real_instrument_vetoed(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, instrument_symbol="NIFTY-FUT", margin_per_lot=D("100000")))
    assert VetoCode.INSTRUMENT_UNVERIFIED in d.codes()


def test_unknown_instrument_vetoed(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, instrument_symbol="NOPE"))
    assert VetoCode.INSTRUMENT_UNKNOWN in d.codes()


def test_futures_without_margin_vetoed(atlas, clock):
    d, _ = atlas.evaluate(
        cand(clock, instrument_symbol="SYNTH-GOLD-MINI", entry=D("70000"), stop=D("69990"), targets=(D("70030"),))
    )
    assert VetoCode.MARGIN_UNKNOWN in d.codes()


def test_futures_margin_beyond_capital(atlas, clock):
    d, _ = atlas.evaluate(
        cand(
            clock,
            instrument_symbol="SYNTH-GOLD-MINI",
            entry=D("70000"),
            stop=D("69990"),
            targets=(D("70030"),),
            est_slippage_per_unit=D("1"),
            est_fixed_costs=D("10"),
            margin_per_lot=D("9000"),
        )
    )
    assert VetoCode.INSUFFICIENT_CAPITAL in d.codes()


def test_costs_exceeding_budget_vetoed(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, est_fixed_costs=D("100")))
    assert VetoCode.COSTS_EXCEED_BUDGET in d.codes()


def test_capital_caps_quantity_without_raising_risk(atlas, clock):
    # tight stop → risk allows 2000 units, but only floor(5000/120)=41 are affordable
    d, _ = atlas.evaluate(cand(clock, stop=D("119.95"), est_slippage_per_unit=D("0"), est_fixed_costs=D("0")))
    assert d.sizing.quantity == 41 and d.sizing.binding_constraint == "CAPITAL"


def test_reserve_never_counts_as_tradable(atlas, clock):
    atlas.record_simulated_realization("W1", "1000", "0")  # +700 trading, +300 reserve
    rs = atlas.risk_state()
    assert rs.reserve == D("300.00") and rs.trading_capital == D("5700.00")
    assert rs.per_trade_budget == D("5700.00") * D("0.02")


def test_paused_mode_vetoes(tmp_path, clock):
    root = make_root(tmp_path)
    a = Atlas(root, tmp_path / "h", clock=clock)
    a.init()
    a.record_simulated_realization("L1", "-800", "0")  # 16% drawdown > 15%
    d, _ = a.evaluate(cand(clock))
    assert VetoCode.RISK_MODE_PAUSED in d.codes()
    a.close()


def test_simulation_fixtures_disabled_outside_simulation(tmp_path, clock):
    from atlas.runtime.service import AtlasError

    root = make_root(tmp_path, {"config/atlas.toml": [('mode = "SIMULATION"', 'mode = "PAPER"')]})
    a = Atlas(root, tmp_path / "h", clock=clock)
    a.init()
    with pytest.raises(AtlasError):
        a.record_simulated_realization("X", "10", "0")
    d, _ = a.evaluate(cand(clock))
    assert VetoCode.SYNTHETIC_DATA_NOT_ALLOWED in d.codes() or VetoCode.INSTRUMENT_UNKNOWN in d.codes()
    a.close()
