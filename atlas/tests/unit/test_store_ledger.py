import sqlite3
from decimal import Decimal

import pytest

from atlas.events.model import EventType, NewEvent
from atlas.ledger.capital import LedgerError, LedgerState, allocate
from atlas.state.store import EventStore


@pytest.fixture
def store(tmp_path, clock):
    s = EventStore(tmp_path / "e.sqlite3", clock, "test")
    s.set_config_context("cfg-test", "f" * 64)
    yield s
    s.close()


def test_append_and_chain(store):
    for i in range(5):
        store.append(NewEvent(EventType.DEPOSIT, {"amount": str(i + 1)}))
    rep = store.verify_chain()
    assert rep.ok and rep.events_checked == 5


def test_idempotency_key_dedupes(store):
    a = store.append(NewEvent(EventType.CANDIDATE_RECEIVED, {"candidate_id": "X"}, idempotency_key="k"))
    b = store.append(NewEvent(EventType.CANDIDATE_RECEIVED, {"candidate_id": "X"}, idempotency_key="k"))
    assert not a.duplicate and b.duplicate and b.event.seq == a.event.seq
    assert store.count() == 1


def test_events_are_immutable(store):
    store.append(NewEvent(EventType.DEPOSIT, {"amount": "1"}))
    with pytest.raises(sqlite3.DatabaseError):
        store._conn.execute("UPDATE events SET payload = '{}'")
    with pytest.raises(sqlite3.DatabaseError):
        store._conn.execute("DELETE FROM events")


def test_out_of_band_tamper_detected(store):
    store.append(NewEvent(EventType.DEPOSIT, {"amount": "1"}))
    store.append(NewEvent(EventType.DEPOSIT, {"amount": "2"}))
    store._conn.execute("DROP TRIGGER events_no_update")
    store._conn.execute("""UPDATE events SET payload = '{"amount":"999"}' WHERE seq = 1""")
    rep = store.verify_chain()
    assert not rep.ok and rep.broken_at_seq == 1


# ------------------------------------------------------------------ ledger


def test_allocation_identity_holds_across_many_values():
    share = Decimal("0.30")
    for paise in range(-50000, 50001, 37):
        gross = Decimal(paise) / 100
        a = allocate(gross, Decimal("3.33"), share)
        assert a.reserve_allocation + a.compound_allocation == a.net_pnl
        if a.net_pnl > 0:
            assert a.reserve_allocation >= 0 and a.compound_allocation >= 0
        else:
            assert a.reserve_allocation == 0


def test_negative_costs_refused():
    with pytest.raises(LedgerError):
        allocate(Decimal("10"), Decimal("-1"), Decimal("0.3"))


def test_withdrawal_limits():
    led = LedgerState()
    led.initialize(Decimal("5000"))
    with pytest.raises(LedgerError):
        led.withdraw(Decimal("1"), "RESERVE")
    with pytest.raises(LedgerError):
        led.withdraw(Decimal("6000"), "TRADING")


def test_deposit_raises_peak_so_drawdown_is_not_masked():
    led = LedgerState()
    led.initialize(Decimal("5000"))
    led.realize(allocate(Decimal("-500"), Decimal("0"), Decimal("0.3")))
    dd_before = led.drawdown_pct
    led.deposit(Decimal("1000"))
    assert led.peak_trading_capital == Decimal("6000")
    assert led.drawdown_pct > 0 and dd_before == Decimal("0.1")
