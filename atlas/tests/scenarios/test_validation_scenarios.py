"""Validation-harness scenarios from skill/references/validation-tests.md.

Each test is tagged with its scenario id. Phase 1 can only exercise the Risk-Engine /
ledger / state half of most scenarios; `scripts/validation_report.py` reports coverage
honestly (FULL vs PARTIAL) using tests/validation_registry.py.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from helpers import cand, sim_position

from atlas.domain.enums import Direction, Provenance, RiskMode, RiskVerdict, RuntimeState, VetoCode
from atlas.synthetic import synthetic_candidate

D = Decimal
sc = pytest.mark.scenario


@sc("T001")
def test_T001_valid_long_can_pass_risk(atlas, clock):
    d, _ = atlas.evaluate(synthetic_candidate("pass-long-equity", clock.now_utc()))
    assert d.verdict is RiskVerdict.RISK_PASS and d.sizing.quantity > 0
    assert d.requires_user_approval and not d.executable


@sc("T002")
def test_T002_valid_short_can_pass_risk(atlas, clock):
    d, _ = atlas.evaluate(synthetic_candidate("pass-short-equity", clock.now_utc()))
    assert d.verdict is RiskVerdict.RISK_PASS and d.sizing.quantity > 0


@sc("T004")
def test_T004_futures_lot_exceeding_risk_rejected(atlas, clock):
    d, _ = atlas.evaluate(synthetic_candidate("futures-min-lot-overflow", clock.now_utc()))
    assert VetoCode.MIN_LOT_EXCEEDS_RISK_BUDGET in d.codes()
    assert d.sizing.lots == 0 and d.sizing.quantity == 0  # never a fractional lot


@sc("T005")
def test_T005_affordable_verified_option_can_pass(atlas, clock):
    d, _ = atlas.evaluate(synthetic_candidate("option-affordable", clock.now_utc()))
    assert d.verdict is RiskVerdict.RISK_PASS
    assert d.sizing.worst_case_loss <= d.budget.applied_budget


@sc("T006")
def test_T006_option_pricing_unavailable_rejected(atlas, clock):
    c = synthetic_candidate("option-affordable", clock.now_utc())
    c = c.model_copy(update={"market_data": c.market_data.model_copy(update={"provenance": Provenance.UNKNOWN})})
    d, _ = atlas.evaluate(c)
    assert d.vetoed and VetoCode.DATA_PROVENANCE_UNKNOWN in d.codes()


@sc("T007")
def test_T007_stale_execution_data_rejected(atlas, clock):
    d, _ = atlas.evaluate(cand(clock, as_of=clock.now_utc() - timedelta(seconds=61)))
    assert VetoCode.STALE_DATA in d.codes()
    d2, _ = atlas.evaluate(cand(clock, as_of=clock.now_utc() - timedelta(seconds=30)))
    assert VetoCode.STALE_DATA not in d2.codes()


@sc("T011")
def test_T011_daily_loss_ceiling_blocks_new_risk(atlas, clock):
    atlas.record_simulated_realization("L1", "-260", "0")  # ceiling = 5% × 5000 = 250
    d, _ = atlas.evaluate(cand(clock))
    assert VetoCode.DAILY_LOSS_CEILING in d.codes()


@sc("T011")
def test_T011_partial_daily_headroom_shrinks_budget(atlas, clock):
    atlas.record_simulated_realization("L1", "-200", "0")  # 50 headroom left
    d, _ = atlas.evaluate(cand(clock))
    assert d.budget.applied_budget == d.budget.daily_headroom
    assert d.sizing.planned_risk <= d.budget.daily_headroom


@sc("T011")
def test_T011_ceiling_resets_next_trading_day(atlas, clock):
    atlas.record_simulated_realization("L1", "-260", "0")
    clock.advance(days=1)
    d, _ = atlas.evaluate(cand(clock))
    assert VetoCode.DAILY_LOSS_CEILING not in d.codes()


@sc("T012")
def test_T012_third_position_rejected(atlas, clock):
    atlas.open_simulated_position(sim_position("P1", underlying="GOLD", risk="30"))
    atlas.open_simulated_position(sim_position("P2", underlying="CRUDEOIL", risk="30"))
    d, _ = atlas.evaluate(cand(clock))
    assert VetoCode.MAX_POSITIONS in d.codes()


@sc("T013")
def test_T013_correlated_second_position_reduced(atlas, clock):
    # open NIFTY risk 60 → BANKNIFTY (same cluster) gets only the remaining 40
    atlas.open_simulated_position(sim_position("P1", underlying="NIFTY", risk="60"))
    c = synthetic_candidate("option-affordable", clock.now_utc())  # BANKNIFTY put
    d, _ = atlas.evaluate(c)
    assert d.budget.cluster == "INDIA_EQUITY_INDEX"
    assert d.budget.applied_budget == D("40")


@sc("T013")
def test_T013_correlated_second_position_rejected_when_budget_used(atlas, clock):
    atlas.open_simulated_position(sim_position("P1", underlying="NIFTY", risk="100"))
    d, _ = atlas.evaluate(synthetic_candidate("option-affordable", clock.now_utc()))
    assert VetoCode.CORRELATION_BUDGET_EXHAUSTED in d.codes()


@sc("T013")
def test_T013_uncorrelated_second_position_not_reduced(atlas, clock):
    atlas.open_simulated_position(sim_position("P1", underlying="GOLD", risk="40"))
    d, _ = atlas.evaluate(synthetic_candidate("option-affordable", clock.now_utc()))
    assert d.budget.cluster_headroom is None and d.budget.applied_budget == D("100")


@sc("T017")
def test_T017_losing_streak_reduces_risk(atlas, clock):
    for i in range(3):
        atlas.record_simulated_realization(f"L{i}", "-10", "0")
    rs = atlas.risk_state()
    assert rs.mode is RiskMode.REDUCED and rs.effective_risk_pct < D("0.02")
    for i in range(3, 5):
        atlas.record_simulated_realization(f"L{i}", "-10", "0")
    assert atlas.risk_state().mode is RiskMode.DEFENSIVE


@sc("T017")
def test_T017_drawdown_bands(atlas):
    atlas.record_simulated_realization("DD", "-450", "0")  # 9% drawdown, 1 loss
    rs = atlas.risk_state()
    assert rs.mode is RiskMode.DEFENSIVE and rs.mode_multiplier == D("0.50")


@sc("T018")
def test_T018_winning_streak_does_not_increase_risk(atlas, clock):
    for i in range(6):
        atlas.record_simulated_realization(f"W{i}", "10", "0")
    rs = atlas.risk_state()
    assert rs.mode is RiskMode.NORMAL and rs.mode_multiplier == D("1.00")
    assert rs.effective_risk_pct == D("0.02")
    d, _ = atlas.evaluate(cand(clock))
    assert any("NOT increased" in n for n in d.notes)


@sc("T019")
def test_T019_restart_with_open_position_recovers(atlas, reopen, clock):
    atlas.open_simulated_position(sim_position("P1", underlying="NIFTY", risk="60"))
    atlas.close()
    b = reopen()
    rep = b.start()
    assert rep.runtime_state is RuntimeState.READY
    assert "P1" in b.state.open_positions
    d, _ = b.evaluate(synthetic_candidate("option-affordable", clock.now_utc()))
    assert d.budget.open_risk == D("60")  # risk recalculated from recovered position


@sc("T022")
def test_T022_duplicate_candidate_event_deduplicated(atlas, clock):
    c = cand(clock)
    d1, dup1 = atlas.evaluate(c)
    n = atlas.store.count()
    d2, dup2 = atlas.evaluate(c)
    assert not dup1 and dup2 and d1.decision_id == d2.decision_id
    assert atlas.state.decisions["RISK_PASS"] + atlas.state.decisions["VETO"] == 1
    assert atlas.store.count() == n + 1  # only a DUPLICATE_SUPPRESSED audit event is added


@sc("T024")
def test_T024_cheap_option_trap_rejected(atlas, clock):
    d, _ = atlas.evaluate(synthetic_candidate("cheap-option-trap", clock.now_utc()))
    assert d.vetoed
    assert d.codes() & {VetoCode.MIN_LOT_EXCEEDS_RISK_BUDGET, VetoCode.WORST_CASE_LOSS_EXCEEDS_BUDGET}


@sc("T024")
def test_T024_option_worst_case_gap_loss_caps_size(atlas, clock):
    # risk-by-stop would allow 6 units; full-premium gap loss allows only 1
    d, _ = atlas.evaluate(synthetic_candidate("option-affordable", clock.now_utc()))
    assert d.sizing.max_quantity_by_risk == 6 and d.sizing.quantity == 1
    assert d.sizing.binding_constraint == "WORST_CASE"


@sc("T031")
def test_T031_profit_allocation_30_70(atlas):
    atlas.record_simulated_realization("W1", "1000", "100")  # net 900
    led = atlas.state.ledger
    assert led.net_realized_pnl == D("900.00")
    assert led.reserve == D("270.00") and led.reserve_allocated == D("270.00")
    assert led.trading_capital == D("5630.00")
    assert not led.invariant_errors()


@sc("T031")
def test_T031_costs_deducted_before_allocation(atlas):
    atlas.record_simulated_realization("W1", "50", "60")  # gross win, net loss
    led = atlas.state.ledger
    assert led.reserve == 0 and led.trading_capital == D("4990.00")
    assert atlas.state.consecutive_losses == 1


@sc("T032")
def test_T032_loss_reduces_trading_capital_only(atlas):
    atlas.record_simulated_realization("W1", "1000", "0")
    atlas.record_simulated_realization("L1", "-400", "0")
    led = atlas.state.ledger
    assert led.reserve == D("300.00") and led.trading_capital == D("5300.00")


@sc("T032")
def test_T032_close_simulated_position_realizes_pnl(atlas, clock):
    c = cand(clock)
    d, _ = atlas.evaluate(c)
    atlas.open_simulated_from_decision(c, d, "POS1")
    atlas.close_simulated_position("POS1", "117.50", "15")  # stopped out: 33 × −2.50 − 15
    led = atlas.state.ledger
    assert led.net_realized_pnl == D("-97.50")
    assert "POS1" not in atlas.state.open_positions


@sc("T033")
def test_T033_deposit_is_capital_not_profit(atlas):
    atlas.deposit("2000")
    led = atlas.state.ledger
    assert led.trading_capital == D("7000.00") and led.reserve == 0
    assert led.net_realized_pnl == 0 and led.reserve_allocated == 0


@sc("T034")
def test_T034_reserve_isolated_from_trading(atlas, clock):
    atlas.record_simulated_realization("W1", "10000", "0")  # reserve 3000, trading 12000
    atlas.record_simulated_realization("L1", "-11000", "0")  # trading 1000, reserve untouched
    led = atlas.state.ledger
    assert led.reserve == D("3000.00") and led.trading_capital == D("1000.00")
    rs = atlas.risk_state()
    assert rs.per_trade_budget == D("1000.00") * rs.effective_risk_pct
    d, _ = atlas.evaluate(cand(clock))
    if d.sizing:
        assert d.sizing.capital_outlay <= D("1000.00")


@sc("T020")
def test_T020_unexpected_position_halts(atlas, reopen):
    from atlas.domain.schemas import model_to_payload
    from atlas.events.model import EventType, NewEvent

    pos = sim_position("GHOST").model_copy(update={"provenance": Provenance.LIVE_VERIFIED, "direction": Direction.SHORT})
    atlas.store.append(NewEvent(EventType.POSITION_OPENED, {"position": model_to_payload(pos)}))
    atlas.close()
    rep = reopen().start()
    assert rep.runtime_state is RuntimeState.HALTED


@sc("T034")
def test_T034_reserve_not_used_for_capital_outlay(atlas, clock):
    atlas.record_simulated_realization("W1", "1000", "0")  # trading 5700, reserve 300
    d, _ = atlas.evaluate(cand(clock, stop=D("119.95"), est_slippage_per_unit=D("0"), est_fixed_costs=D("0")))
    # affordable from trading capital only: floor(5700 / 120) = 47 (reserve would make it 50)
    assert d.sizing.binding_constraint == "CAPITAL" and d.sizing.quantity == 47
