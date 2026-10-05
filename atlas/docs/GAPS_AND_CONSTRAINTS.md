# Available technology, constraints, and what is missing / unverifiable

Status as of Phase 1 (2026-10-05). Nothing below is assumed to exist until verified.

## Available

| Item | Status |
|---|---|
| Python 3.11+ (built/tested on 3.13) | used |
| SQLite (stdlib) | event store + snapshots |
| pydantic v2 | typed schemas / config validation |
| pytest | tests |
| numpy / pandas / scipy / statsmodels | Phase 3 (Quant) — not yet a dependency |

## Data sources — NONE connected yet

| Need | Candidate source | Verified? |
|---|---|---|
| Live index/futures/option quotes (NSE/BSE) | Broker API (e.g. Zerodha Kite Connect, paid), NSE feed vendors | **No** |
| Option chain with bid/ask, OI, IV, Greeks | Broker API / vendor | **No** — required before any option trade can pass |
| MCX Gold/Silver/Crude quotes | Broker API / vendor | **No** |
| Historical point-in-time option bid/ask | Vendor | **No** — without it, historical option replay must be refused |
| EOD prices | yfinance / NSE bhavcopy | Unofficial/EOD only — not execution-grade |
| Economic calendar / news | TBD | **No** |

Consequence: until a verified feed exists, every non-synthetic candidate is vetoed for
`DATA_UNVERIFIED`. This is correct behaviour, not a bug.

## Execution

* TradingView Paper Trading has **no public API** we can rely on → treated as a
  *human-in-the-loop* venue (user places the paper order, then records fill evidence).
* No broker adapter exists. No live-money path will be built until the conditions in
  `skill/SKILL.md` "Current implementation boundary" are met.

## Unverifiable / must be supplied by the user

1. **Exchange contract specs** — lot sizes, tick sizes, multipliers, expiry calendars for
   NIFTY, BANKNIFTY, FINNIFTY, SENSEX, MCX Gold/Silver/Crude. These change by exchange
   circular. `config/instruments.toml` ships with `lot_size = 0` and `verified = false`;
   the Risk Engine vetoes any unverified instrument.
2. **Margin requirements** — broker/SPAN-dependent; not computable offline.
3. **Cost schedule** — brokerage plan, STT/CTT, exchange txn charges, GST, SEBI fee,
   stamp duty rates. Needed for Phase 4 cost model; must be entered from current
   official schedules with an effective date.
4. **Risk-mode multipliers** — the skill defines drawdown/streak *bands* but not how much
   to cut risk in each. Phase 1 defaults (configurable, versioned): REDUCED 0.75,
   DEFENSIVE 0.50, VERY_DEFENSIVE 0.25, PAUSED 0. **Please confirm.**
5. **Correlation clusters** — Phase 1 treats NIFTY/BANKNIFTY/FINNIFTY/SENSEX as one
   cluster sharing one per-trade risk budget (`cluster_risk_multiple = 1.0`). Gold/Silver
   are a second cluster; Crude stands alone. **Please confirm.**
6. **Data freshness limits** — Phase 1 defaults: intraday 60 s, swing 1 day. Confirm.
7. **Regulatory** — retail F&O eligibility, any algo-trading registration requirements
   for future broker automation must be checked by the user before Phase 11+.

## Known limitations of Phase 1

* No market data, opportunity detection, quant, instrument search, execution, monitor,
  journal or UI. Positions can only enter the store via test fixtures.
* "Daily" uses IST (UTC+05:30, no DST) calendar days; exchange holiday calendar not loaded.
* Single-process; no concurrent writers.
