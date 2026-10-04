from decimal import Decimal

import pytest
from helpers import cand, make_root, sim_position

from atlas.domain.enums import Provenance, RuntimeState
from atlas.domain.schemas import model_to_payload
from atlas.events.model import EventType, NewEvent
from atlas.runtime.service import Atlas, AtlasHalted


def _populate(a: Atlas, clock):
    a.deposit("1000", "top-up")
    a.record_simulated_realization("W1", "250", "20")
    a.evaluate(cand(clock))
    a.open_simulated_position(sim_position("P1"))


def test_restart_recovers_identical_state(atlas, reopen, clock):
    _populate(atlas, clock)
    before = atlas.state.to_dict()
    atlas.close()
    b = reopen()
    rep = b.start()
    assert rep.runtime_state is RuntimeState.READY, rep.halt_reasons
    after = b.state.to_dict()
    for k in ("ledger", "open_positions", "consecutive_losses", "decisions", "kill_switch"):
        assert after[k] == before[k]


def test_tampered_event_halts(atlas, reopen, clock):
    _populate(atlas, clock)
    atlas.store._conn.execute("DROP TRIGGER events_no_update")
    atlas.store._conn.execute(
        """UPDATE events SET payload = '{"amount":"100000","note":"x"}' WHERE type = 'DEPOSIT'"""
    )
    atlas.close()
    b = reopen()
    rep = b.start()
    assert rep.runtime_state is RuntimeState.HALTED
    assert any("verify_event_chain" in r for r in rep.halt_reasons)
    with pytest.raises(AtlasHalted):
        b.deposit("1")


def test_tampered_snapshot_halts(atlas, reopen, clock):
    _populate(atlas, clock)
    atlas.store._conn.execute(
        "UPDATE snapshots SET state = replace(state, '\"6000.00\"', '\"9999.00\"')"
    )
    atlas.store._conn.execute("UPDATE snapshots SET state_hash = 'x' WHERE snapshot_seq = (SELECT max(snapshot_seq) FROM snapshots)")
    atlas.close()
    rep = reopen().start()
    assert rep.runtime_state is RuntimeState.HALTED
    assert any("compare_snapshot" in r for r in rep.halt_reasons)


def test_config_drift_without_version_bump_halts(atlas, tmp_path, home, clock):
    atlas.close()
    root2 = make_root(tmp_path / "v2", {"config/atlas.toml": [('risk_per_trade_pct = "0.02"', 'risk_per_trade_pct = "0.01"')]})
    b = Atlas(root2, home, clock=clock)
    rep = b.start()
    assert rep.runtime_state is RuntimeState.HALTED
    assert any("WITHOUT a version bump" in r for r in rep.halt_reasons)
    with pytest.raises(Exception):
        b.approve_config("try to sneak it in")
    b.close()


def test_version_bump_requires_explicit_approval(atlas, tmp_path, home, clock):
    atlas.close()
    root2 = make_root(
        tmp_path / "v2",
        {
            "config/atlas.toml": [
                ('risk_per_trade_pct = "0.02"', 'risk_per_trade_pct = "0.01"'),
                ('config_version = "1.0.0"', 'config_version = "1.1.0"'),
            ]
        },
    )
    b = Atlas(root2, home, clock=clock)
    rep = b.start()
    assert rep.runtime_state is RuntimeState.HALTED
    d, _ = b.evaluate(cand(clock))
    assert d.vetoed  # halted runtime → SYSTEM_NOT_READY
    rep2 = b.approve_config("halve risk while paper validation runs")
    assert rep2.runtime_state is RuntimeState.READY
    assert b.risk_state().per_trade_budget == Decimal("50.0000")
    b.close()


def test_kill_switch_persists_across_restart(atlas, reopen):
    atlas.set_kill_switch(True, "manual stop")
    atlas.close()
    rep = reopen().start()
    assert rep.runtime_state is RuntimeState.HALTED


def test_unreconcilable_position_halts(atlas, reopen):
    pos = sim_position("REAL-1").model_copy(update={"provenance": Provenance.LIVE_VERIFIED})
    # simulate an externally-injected (non-synthetic) position record
    atlas.store.append(NewEvent(EventType.POSITION_OPENED, {"position": model_to_payload(pos)}))
    atlas.close()
    rep = reopen().start()
    assert rep.runtime_state is RuntimeState.HALTED
    assert any("reconcile_positions" in r for r in rep.halt_reasons)


def test_impossible_pnl_record_halts(atlas, reopen):
    atlas.store.append(
        NewEvent(
            EventType.TRADE_REALIZED,
            {
                "trade_id": "BAD",
                "reserve_share": "0.30",
                "gross_pnl": "100.00",
                "costs": "0.00",
                "net_pnl": "100.00",
                "reserve_allocation": "0.00",  # should be 30.00
                "compound_allocation": "100.00",
            },
        )
    )
    atlas.close()
    rep = reopen().start()
    assert rep.runtime_state is RuntimeState.HALTED
    assert any("impossible P&L" in r for r in rep.halt_reasons)


def test_reinit_refused(atlas):
    from atlas.runtime.service import AtlasError

    with pytest.raises(AtlasError):
        atlas.init()
