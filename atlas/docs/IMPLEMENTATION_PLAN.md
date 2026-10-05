# ATLAS Implementation Plan

Vertical slices. Each phase ends with: tests green, validation report regenerated,
demo script, and a tagged commit. No phase may weaken a gate built by an earlier phase.

| Phase | Scope | Exit criteria | Validation scenarios unlocked |
|---|---|---|---|
| **1 ✅** | Repo, Constitution + config versioning, schemas, event model, hash-chained event store, snapshots, capital ledger, Risk Engine, bootstrap/recovery, CLI | Phase 1 demo passes; tamper/config-drift → HALT | T004*, T007*, T011, T012, T013, T017, T018, T019*, T022*, T031–T034 |
| 2 | `MarketDataPort` + first real adapter, DQS, Market State Engine (5m→Daily), Opportunity Engine (lifecycle, LONG/SHORT independent), event priorities | DQS separates freshness/completeness/consistency; stale feed → NO TRADE | T003, T007, T008, T023, T026, T027 |
| 3 | Quant Engine (statsmodels AR/ARIMA/Markov switching, vol), Monte Carlo P(target-before-stop), QES, EV engine, Decision Engine gates (conf ≥ 70, EV > 0, R:R ≥ 1.5), UNKNOWN propagation | Insufficient sample → UNKNOWN → veto | T001, T002, T009, T010, T028, T029 |
| 4 | Instrument search (cash → futures → long options → debit spreads), verified contract specs, cost model (statutory charges + slippage), liquidity checks | Min-lot overflow triggers alternative search, not fractional lots | T004, T005, T006, T024 |
| 5 | `ExecutionPort`, ManualPaperAdapter (TradingView human venue with fill evidence), order FSM, approval workflow, reconciliation, partial fills | No fill without evidence; mismatch → HALT | T014, T015, T020, T021 |
| 6 | Position monitor (GREEN/YELLOW/RED, time stops, no stop widening), event detector/filter/coalescer, cooldowns, kill switch runtime | P0 preempts; duplicate events never duplicate orders | T016, T019, T022, T025 |
| 7 | Journal, prediction ledger, Brier score + buckets, trade grades A–E, strategy scorecards, decay detector | Calibration degradation → WATCH/suspend; no auto rule change | T030, T035–T038 |
| 8 | Cockpit UI (FastAPI + static frontend) bound to backend state; WHY ATLAS / APPROVE / REJECT / MONITOR / EXIT map to real transitions | No button without a backend transition | UI consistency tests |
| 9 | Full validation suite + failure injection | All 38 scenarios PASS or justified BLOCKED | all |
| 10 | Historical replay with point-in-time snapshots | Hindsight contamination rejected | T030 |
| 11 | Controlled paper trading | ≥ 50 paper trades before any review | — |

`*` = partial coverage in Phase 1 (the Risk-Engine half of the scenario).

## Decisions needed from the user before Phase 2

1. Market data vendor / broker API for live quotes and option chains.
2. Confirm risk-mode multipliers and correlation clusters (see GAPS_AND_CONSTRAINTS.md).
3. Verified contract specs for the primary universe (lot sizes are exchange circular driven).
