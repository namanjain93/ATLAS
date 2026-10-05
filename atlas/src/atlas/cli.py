"""ATLAS command-line interface (Phase 1).

    atlas init                      create the event store, approve config, open the ledger
    atlas start                     run startup/recovery and print the report
    atlas status | capital | risk   read-only views
    atlas synth-candidate SCENARIO  write a SYNTHETIC candidate (stamped now) as JSON
    atlas evaluate FILE             submit a candidate to the Risk Engine
    atlas deposit AMOUNT            add capital (not profit)
    atlas withdraw AMOUNT --source reserve|trading
    atlas kill on|off --reason ...  kill switch
    atlas config approve --reason   approve a new (version-bumped) configuration
    atlas audit [--tail N]          verify the hash chain and show recent events

Global options: --root (repo/config root, default: cwd), --home (state dir, default: ./atlas_home
or $ATLAS_HOME).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from atlas.config.models import ConfigError
from atlas.domain.money import fmt_inr, fmt_pct
from atlas.domain.schemas import RiskDecision, TradeCandidate
from atlas.ledger.capital import LedgerError
from atlas.runtime.service import Atlas, AtlasError, RecoveryReport
from atlas.synthetic import SCENARIOS, synthetic_candidate

_ICON = {"OK": "✔", "HALT": "✖", "NOT_AVAILABLE": "–"}


def _print_report(rep: RecoveryReport) -> None:
    print("ATLAS startup / recovery")
    for s in rep.steps:
        print(f"  {_ICON.get(s.status, '?')} {s.name:<22} {s.status:<13} {s.detail}")
    print(f"  → runtime state: {rep.runtime_state.value}")
    for r in rep.halt_reasons:
        print(f"    HALT: {r}")


def _print_capital(a: Atlas) -> None:
    led = a.state.ledger
    print("Capital ledger")
    rows = [
        ("Trading capital", fmt_inr(led.trading_capital)),
        ("Reserve (not tradable)", fmt_inr(led.reserve)),
        ("Peak trading capital", fmt_inr(led.peak_trading_capital)),
        ("Initial capital", fmt_inr(led.initial_capital)),
        ("Deposits", fmt_inr(led.deposits)),
        ("Withdrawals", fmt_inr(led.withdrawals)),
        ("Gross realized P&L", fmt_inr(led.gross_realized_pnl)),
        ("Costs", fmt_inr(led.costs)),
        ("Net realized P&L", fmt_inr(led.net_realized_pnl)),
        ("  → to reserve (30%)", fmt_inr(led.reserve_allocated)),
        ("  → compounded (70%)", fmt_inr(led.compound_allocated)),
    ]
    for k, v in rows:
        print(f"  {k:<26} {v:>14}")
    errs = led.invariant_errors()
    print(f"  identity check: {'OK' if not errs else '; '.join(errs)}")


def _print_risk(a: Atlas) -> None:
    rs = a.risk_state()
    print("Risk budget")
    rows = [
        ("Risk mode", rs.mode.value + (f"  ({'; '.join(rs.mode_reasons)})" if rs.mode_reasons else "")),
        ("Base risk / trade", fmt_pct(rs.base_risk_pct)),
        ("Mode multiplier", str(rs.mode_multiplier)),
        ("Effective risk / trade", fmt_pct(rs.effective_risk_pct)),
        ("Per-trade risk budget", fmt_inr(rs.per_trade_budget)),
        ("Daily loss ceiling", fmt_inr(rs.daily_loss_ceiling) + f"  (day-open {fmt_inr(rs.day_open_capital)})"),
        ("Daily realized P&L", fmt_inr(rs.daily_realized_pnl)),
        ("Open risk", fmt_inr(rs.open_risk)),
        ("Daily headroom", fmt_inr(rs.daily_headroom)),
        ("Drawdown from peak", fmt_pct(rs.drawdown_pct)),
        ("Consecutive losses", str(rs.consecutive_losses)),
        ("Open positions", f"{len(rs.open_positions)} / {a.cfg.risk.max_concurrent_positions}"),
        ("Kill switch", "ACTIVE" if rs.kill_switch else "off"),
        ("Runtime", a.runtime_state.value),
    ]
    for k, v in rows:
        print(f"  {k:<24} {v}")


def print_decision(d: RiskDecision, duplicate: bool = False) -> None:
    head = "DUPLICATE — original decision returned" if duplicate else "Risk Engine decision"
    print(f"{head}: {d.verdict.value}  (candidate {d.candidate_id})")
    print(f"  mode={d.risk_mode.value} synthetic={d.synthetic} executable={d.executable} "
          f"user_approval_required={d.requires_user_approval}")
    if d.budget:
        b = d.budget
        print(f"  budget: per-trade {fmt_inr(b.per_trade_budget)} · daily headroom {fmt_inr(b.daily_headroom)}"
              + (f" · cluster {b.cluster} headroom {fmt_inr(b.cluster_headroom)}" if b.cluster_headroom is not None else "")
              + f" → applied {fmt_inr(b.applied_budget)}")
    if d.sizing:
        s = d.sizing
        print(f"  sizing: risk/unit {fmt_inr(s.risk_per_unit)} · max qty by risk {s.max_quantity_by_risk} · "
              f"lots {s.lots} · qty {s.quantity} · planned risk {fmt_inr(s.planned_risk)} · "
              f"outlay {fmt_inr(s.capital_outlay)} · binding {s.binding_constraint}")
    for r in d.reasons:
        print(f"  VETO {r.code.value}: {r.detail}")
    for n in d.notes:
        print(f"  note: {n}")


def _load_candidate(path: str) -> TradeCandidate:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh, parse_float=Decimal)
    return TradeCandidate.model_validate(raw)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atlas", description="ATLAS Phase 1 — risk-first core")
    p.add_argument("--root", default=os.environ.get("ATLAS_ROOT", "."))
    p.add_argument("--home", default=os.environ.get("ATLAS_HOME", "atlas_home"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("start")
    sub.add_parser("status")
    sub.add_parser("capital")
    sub.add_parser("risk")
    sc = sub.add_parser("synth-candidate")
    sc.add_argument("scenario", choices=SCENARIOS)
    sc.add_argument("-o", "--output")
    ev = sub.add_parser("evaluate")
    ev.add_argument("file")
    dp = sub.add_parser("deposit")
    dp.add_argument("amount")
    dp.add_argument("--note", default="")
    wd = sub.add_parser("withdraw")
    wd.add_argument("amount")
    wd.add_argument("--source", choices=["reserve", "trading"], required=True)
    wd.add_argument("--note", default="")
    k = sub.add_parser("kill")
    k.add_argument("state", choices=["on", "off"])
    k.add_argument("--reason", required=True)
    c = sub.add_parser("config")
    c.add_argument("action", choices=["approve"])
    c.add_argument("--reason", required=True)
    au = sub.add_parser("audit")
    au.add_argument("--tail", type=int, default=10)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        atlas = Atlas(args.root, args.home)
    except ConfigError as exc:
        print(f"CONFIG REFUSED: {exc}", file=sys.stderr)
        return 2
    try:
        if args.cmd == "init":
            _print_report(atlas.init())
            _print_capital(atlas)
            return 0
        if args.cmd == "synth-candidate":
            cand = synthetic_candidate(args.scenario, atlas.now())
            text = json.dumps(cand.model_dump(mode="json"), indent=2)
            if args.output:
                Path(args.output).write_text(text, encoding="utf-8")
                print(f"wrote SYNTHETIC candidate → {args.output}")
            else:
                print(text)
            return 0
        read_only = args.cmd in ("status", "capital", "risk", "audit")
        rep = atlas.start(record=not read_only)
        if args.cmd == "start":
            _print_report(rep)
            return 0 if rep.runtime_state.value == "READY" else 1
        if args.cmd == "status":
            _print_report(rep)
            if atlas.initialized:
                print()
                _print_capital(atlas)
                print()
                _print_risk(atlas)
            return 0
        if args.cmd == "capital":
            _print_capital(atlas)
            return 0
        if args.cmd == "risk":
            _print_risk(atlas)
            return 0
        if args.cmd == "audit":
            chain = atlas.store.verify_chain()
            print(f"hash chain: {'INTACT' if chain.ok else 'BROKEN'} ({chain.events_checked} events) {chain.detail}")
            for e in atlas.store.tail(args.tail):
                print(f"  #{e.seq:<4} {e.ts_utc[:19]} {e.priority.value} {e.type.value:<20} "
                      f"{e.config_version} {e.hash[:12]}")
            return 0 if chain.ok else 1
        if args.cmd == "evaluate":
            if rep.halt_reasons:
                print("note: runtime is HALTED — the Risk Engine will veto.")
            d, dup = atlas.evaluate(_load_candidate(args.file))
            print_decision(d, dup)
            return 0
        if args.cmd == "deposit":
            atlas.deposit(args.amount, args.note)
            _print_capital(atlas)
            return 0
        if args.cmd == "withdraw":
            atlas.withdraw(args.amount, args.source, args.note)
            _print_capital(atlas)
            return 0
        if args.cmd == "kill":
            _print_report(atlas.set_kill_switch(args.state == "on", args.reason))
            return 0
        if args.cmd == "config":
            _print_report(atlas.approve_config(args.reason))
            return 0
    except (AtlasError, ConfigError, LedgerError, ValidationError, ValueError, TypeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    finally:
        atlas.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
