from decimal import Decimal

import pytest
from helpers import make_root

from atlas.config.loader import load_config
from atlas.config.models import ConfigError
from atlas.domain.money import floor_int, to_dec


def test_floor_never_rounds_up():
    assert floor_int(Decimal("33.999999")) == 33
    assert floor_int(Decimal("0.9999")) == 0
    assert floor_int(Decimal("-0.1")) == -1


def test_floats_rejected_for_money():
    with pytest.raises(TypeError):
        to_dec(0.1)


def test_repo_config_loads(root):
    lc = load_config(root)
    assert lc.config.risk.risk_per_trade_pct == Decimal("0.02")
    assert lc.config.risk.max_concurrent_positions == 2
    assert len(lc.fingerprint) == 64


def test_real_instruments_ship_unverified(root):
    lc = load_config(root)
    nifty = lc.instruments.get("NIFTY-FUT")
    assert nifty is not None and nifty.verified is False and nifty.lot_size == 0


@pytest.mark.parametrize(
    "edit",
    [
        ('risk_per_trade_pct = "0.02"', 'risk_per_trade_pct = "0.03"'),
        ('daily_loss_pct = "0.05"', 'daily_loss_pct = "0.10"'),
        ("max_concurrent_positions = 2", "max_concurrent_positions = 3"),
        ('reserve_share = "0.30"', 'reserve_share = "0.20"'),
        ("user_approval_required = true", "user_approval_required = false"),
        ('adapter = "NONE"', 'adapter = "ZERODHA_LIVE"'),
        ('REDUCED = "0.75"', 'REDUCED = "1.25"'),
        ('PAUSED = "0.00"', 'PAUSED = "0.10"'),
        ('cluster_risk_multiple = "1.0"', 'cluster_risk_multiple = "2.0"'),
    ],
)
def test_config_cannot_exceed_constitution(tmp_path, edit):
    root = make_root(tmp_path, {"config/atlas.toml": [edit]})
    with pytest.raises(ConfigError):
        load_config(root)


def test_constitution_non_negotiables_locked(tmp_path):
    root = make_root(
        tmp_path, {"config/constitution.toml": [("live_execution_allowed = false", "live_execution_allowed = true")]}
    )
    with pytest.raises(ConfigError):
        load_config(root)


def test_synthetic_instruments_excluded_outside_simulation(tmp_path):
    root = make_root(tmp_path, {"config/atlas.toml": [('mode = "SIMULATION"', 'mode = "PAPER"')]})
    lc = load_config(root)
    assert lc.instruments.get("SYNTH-EQ") is None
