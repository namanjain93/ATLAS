# ATLAS — Adaptive Trading & Learning Analysis System

A risk-first, direction-neutral, event-sourced trading system for Indian markets
(NSE/BSE index derivatives, MCX commodities). **Paper-only. Every trade needs human
approval. `NO TRADE` is a valid, successful outcome.**

> **Status: Phase 1 of 11 — core backend.** There is no market data, no signal generation and
> no execution in this phase. Every candidate it evaluates is **SYNTHETIC**. Nothing in this repo
> is evidence of profitability.

The behavioural specification is the ATLAS skill package in [`skill/`](skill/SKILL.md).

## What Phase 1 does

| Capability | Where |
|---|---|
| Constitution with hard ceilings (2% risk/trade, 5% daily loss, 2 positions, 30% reserve) that config cannot exceed | `config/constitution.toml`, `src/atlas/config/` |
| Versioned config: any change without a version bump **HALTs**; a bump requires `atlas config approve` | `src/atlas/runtime/service.py` |
| Append-only, SHA-256 hash-chained SQLite event store + snapshots; tampering → **HALT** | `src/atlas/state/store.py` |
| Capital ledger: costs first, 30/70 reserve/compound split, deposits ≠ profit, reserve never tradable | `src/atlas/ledger/capital.py` |
| Deterministic Risk Engine with veto authority: floor-only sizing, min-lot rejection (no fractional lots), daily-loss headroom, max positions, correlation clusters, drawdown & losing-streak modes, data freshness/provenance, instrument verification, option worst-case (gap) loss | `src/atlas/risk/` |
| Startup/recovery: load → verify chain → replay → snapshot check → config approval → reconcile → recalc risk → READY / HALTED | `Atlas.start()` |
| CLI + Phase 1 demo + validation report | `src/atlas/cli.py`, `scripts/` |

## Quick start

Requires Python 3.11+.

```bash
git clone <your-repo-url> atlas && cd atlas
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

python -m pytest                      # unit + scenario tests
python scripts/phase1_demo.py         # end-to-end Phase 1 demonstration
python scripts/validation_report.py   # T001–T038: PASS / FAIL / BLOCKED / NOT IMPLEMENTED
```

## CLI

State lives in `./atlas_home` (override with `--home` or `ATLAS_HOME`).

```bash
atlas init                                   # approve config v1.0.0, open ledger at ₹5,000
atlas status                                 # recovery report + capital + risk budget
atlas synth-candidate pass-long-equity -o c.json   # SYNTHETIC candidate stamped "now"
atlas evaluate c.json                        # Risk Engine: RISK_PASS (sized) or VETO (+ reasons)
atlas deposit 1000 --note "top-up"           # capital, not profit
atlas kill on --reason "manual stop"         # kill switch (persists across restarts)
atlas config approve --reason "..."          # after bumping config_version
atlas audit --tail 20                        # verify hash chain, show recent events
```

Synthetic scenarios: `pass-long-equity`, `pass-short-equity`, `futures-min-lot-overflow`,
`option-affordable`, `cheap-option-trap`, `stale-data`, `invalid-stop`.

`RISK_PASS` means *sized and within limits*. It is **not** a trade authorization: user approval
and a verified execution adapter are still required, and Phase 1 has no execution adapter.

## Before any real instrument can pass

`config/instruments.toml` deliberately ships with `lot_size = 0` and `verified = false`. Fill in
lot size / multiplier / tick size from the **current** exchange circular, set `verified = true`
with `source` and `verified_on`, bump `config_version`, then `atlas config approve`. Until then
the Risk Engine vetoes them (`INSTRUMENT_UNVERIFIED`), and any non-synthetic market data is
vetoed (`DATA_UNVERIFIED`) because no verified data source exists yet.

## Docs

* [Architecture](docs/ARCHITECTURE.md)
* [Implementation plan & milestones](docs/IMPLEMENTATION_PLAN.md)
* [Available technology, constraints, missing/unverifiable items](docs/GAPS_AND_CONSTRAINTS.md)
* [Latest validation report](reports/VALIDATION_REPORT.md)

## Non-goals (until explicitly approved, versioned, and validated)

Live-money execution · autonomous order placement · automatic changes to the Constitution or
risk limits · fabricated prices, fills, probabilities or backtests.

*Not investment advice. This software is an engineering project; it does not guarantee any
trading outcome and must not be used to bypass broker, exchange or regulatory requirements.*
