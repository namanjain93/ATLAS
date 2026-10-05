"""Phase 1 end-to-end demonstration.

ATLAS starts → loads configuration → loads persistent state → displays capital →
calculates risk budget → accepts a SYNTHETIC trade candidate → Risk Engine sizes it →
Risk Engine vetoes others → state is persisted → audit events are created →
system restarts → state is recovered and verified → (failure injection) tampering → HALT.

Usage:  python scripts/phase1_demo.py [--home DIR]
Uses a fresh temporary state directory by default; nothing here is market data.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.cli import _print_capital, _print_report, _print_risk, print_decision  # noqa: E402
from atlas.domain.money import fmt_pct  # noqa: E402
from atlas.runtime.service import DB_NAME, Atlas  # noqa: E402
from atlas.state.store import state_hash  # noqa: E402
from atlas.synthetic import synthetic_candidate  # noqa: E402


def banner(n: int, text: str) -> None:
    print(f"\n{'=' * 78}\n[{n}] {text}\n{'=' * 78}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=None)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # ₹ on Windows consoles
    except Exception:
        pass
    home = Path(args.home) if args.home else Path(tempfile.mkdtemp(prefix="atlas_demo_"))
    if home.exists() and any(home.iterdir()):
        print(f"refusing to reuse non-empty demo home {home}")
        return 2

    banner(1, "ATLAS starts and loads configuration")
    atlas = Atlas(ROOT, home)
    lc = atlas.loaded
    c = lc.constitution.ceilings
    print(f"config {lc.version_label}  fingerprint {lc.fingerprint[:16]}…  mode {atlas.cfg.runtime.mode.value}")
    print(f"constitution ceilings: risk/trade ≤ {fmt_pct(c.max_risk_per_trade_pct)}, daily loss ≤ "
          f"{fmt_pct(c.max_daily_loss_pct)}, positions ≤ {c.max_concurrent_positions}, "
          f"reserve share = {fmt_pct(c.reserve_share_of_net_profit)}")
    unverified = [s.symbol for s in lc.instruments.all() if not s.verified]
    print(f"real instruments awaiting verified exchange specs: {', '.join(unverified)}")

    banner(2, "Load persistent state (first run → initialize ledger)")
    _print_report(atlas.init())

    banner(3, "Capital")
    _print_capital(atlas)

    banner(4, "Risk budget")
    _print_risk(atlas)

    banner(5, "Accept a SYNTHETIC trade candidate → Risk Engine sizes it")
    cand = synthetic_candidate("pass-long-equity", atlas.now())
    print(f"candidate {cand.candidate_id}: {cand.direction.value} {cand.instrument_symbol} "
          f"entry {cand.entry} stop {cand.stop} targets {list(map(str, cand.targets))}")
    d, _ = atlas.evaluate(cand)
    print_decision(d)

    banner(6, "Risk Engine vetoes")
    for scen in ("futures-min-lot-overflow", "cheap-option-trap", "stale-data"):
        print(f"\n— scenario: {scen}")
        d2, _ = atlas.evaluate(synthetic_candidate(scen, atlas.now()))
        print_decision(d2)
    print("\n— duplicate submission of the first candidate")
    d3, dup = atlas.evaluate(cand)
    print_decision(d3, dup)

    banner(7, "SIMULATED outcome (synthetic fixture): realize a trade, keep one position open")
    atlas.open_simulated_from_decision(cand, d, "SIM-1")
    atlas.close_simulated_position("SIM-1", "124.00", "20.00")  # 33 × 4.00 − 20 = 112.00 net
    print("closed SIM-1 at 124.00 with ₹20 costs → net ₹112.00 → reserve 30% / trading 70%")
    opt = synthetic_candidate("option-affordable", atlas.now())
    d_opt, _ = atlas.evaluate(opt)
    print_decision(d_opt)
    atlas.open_simulated_from_decision(opt, d_opt, "SIM-2")
    print("opened SIM-2 (synthetic) — it stays open across the restart")
    _print_capital(atlas)

    banner(8, "State persisted + audit events created")
    chain = atlas.store.verify_chain()
    snap = atlas.store.latest_snapshot()
    print(f"event store: {atlas.store.path}")
    print(f"events: {atlas.store.count()}  hash chain: {'INTACT' if chain.ok else 'BROKEN'}  "
          f"latest snapshot @seq {snap.event_seq if snap else '-'}")
    for e in atlas.store.tail(8):
        print(f"  #{e.seq:<3} {e.priority.value} {e.type.value:<21} {e.hash[:16]}…")
    before = atlas.state.to_dict()
    before_hash = state_hash({k: v for k, v in before.items() if k not in ("last_seq", "last_hash")})
    atlas.close()

    banner(9, "Restart → recover")
    atlas2 = Atlas(ROOT, home)
    rep = atlas2.start()
    _print_report(rep)
    after = atlas2.state.to_dict()
    # the restart itself appends a RUNTIME_STARTED audit event, so compare business state
    after_hash = state_hash({k: v for k, v in after.items() if k not in ("last_seq", "last_hash")})
    ok = before_hash == after_hash
    print(f"\nrecovered state matches pre-restart state: {'YES' if ok else 'NO'} "
          f"({before_hash[:16]}… vs {after_hash[:16]}…)")
    _print_capital(atlas2)
    print()
    _print_risk(atlas2)
    print(f"open positions recovered: {sorted(atlas2.state.open_positions)}")
    atlas2.close()

    banner(10, "Failure injection: out-of-band tampering with a copy of the event store")
    tamper_home = home.parent / (home.name + "_tampered")
    shutil.copytree(home, tamper_home)
    con = sqlite3.connect(tamper_home / DB_NAME)
    con.execute("DROP TRIGGER events_no_update")
    con.execute("""UPDATE events SET payload = replace(payload, '"5000.00"', '"500000.00"')
                   WHERE type = 'LEDGER_INITIALIZED'""")
    con.commit()
    con.close()
    atlas3 = Atlas(ROOT, tamper_home)
    rep3 = atlas3.start()
    _print_report(rep3)
    atlas3.close()

    print(f"\nPhase 1 demo complete. State directory: {home}")
    return 0 if ok and rep.runtime_state.value == "READY" and rep3.runtime_state.value == "HALTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
