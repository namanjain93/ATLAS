# ATLAS — Repository Architecture

Source of truth for behaviour: `skill/` (the ATLAS skill package, frozen copy).
This document maps that specification onto concrete code.

## Design rules (enforced in code, not prompts)

| Rule | Where it is enforced |
|---|---|
| Risk limits cannot exceed the Constitution | `atlas.config.loader` refuses to load a config whose limits exceed `config/constitution.toml` hard ceilings |
| Config changes require explicit versioned approval | `atlas.runtime.bootstrap` HALTs if the config hash changed without a version bump, or a new version has no `CONFIG_APPROVED` event |
| Risk Engine veto authority | `atlas.risk.engine.RiskEngine` is the only producer of `RISK_PASS`; every gate runs, all veto reasons are recorded |
| Always round down | `atlas.domain.money.floor_int`; no other rounding path exists in sizing |
| Reserve unavailable for trading | `RiskEngine` reads only `trading_capital`; the ledger has no reserve→trading transfer |
| No fabricated data | Candidates carry `MarketDataRef` provenance + timestamp; `UNKNOWN`/missing → veto. Instruments without a verified spec → veto |
| Persistent state is truth | SQLite append-only event store (UPDATE/DELETE blocked by triggers), SHA-256 hash chain, projections rebuilt by replay |
| Any inconsistency is a risk event | Hash-chain break, ledger-invariant break, snapshot mismatch, unreconcilable position → `HALTED` |
| No execution in Phase 1 | There is no order/execution module. A `RISK_PASS` is explicitly *not* a trade authorization |

## Layout

```
atlas/
├── config/
│   ├── constitution.toml        # hard ceilings + non-negotiables (versioned)
│   ├── atlas.toml               # operating config (must be ≤ constitution)
│   └── instruments.toml         # exchange specs — ships UNVERIFIED (lot_size = 0)
├── src/atlas/
│   ├── config/                  # typed config models, loader, hashing, constitution check
│   ├── domain/                  # enums, money (Decimal), schemas (candidate, decision, position)
│   ├── events/                  # event envelope, types, priorities
│   ├── state/                   # SQLite event store, snapshots, projections (replay)
│   ├── ledger/                  # capital ledger: deposits, withdrawals, 30/70 allocation
│   ├── risk/                    # modes (drawdown/streak), sizing, gates, RiskEngine
│   ├── runtime/                 # clock, bootstrap/recovery, ATLAS service facade
│   └── cli.py                   # `atlas` command
├── tests/
│   ├── unit/                    # component tests
│   └── scenarios/               # validation-harness tests tagged @scenario("Txxx")
├── scripts/
│   ├── phase1_demo.py           # the end-to-end Phase 1 demonstration
│   └── validation_report.py     # PASS / FAIL / BLOCKED / NOT IMPLEMENTED for T001–T038
├── examples/                    # SYNTHETIC instruments + candidates (labelled as such)
├── docs/                        # architecture, plan, gaps
└── skill/                       # ATLAS skill package (specification)
```

## Future packages (later phases — not present yet)

```
src/atlas/data/        Phase 2  market-data ports + adapters, DQS
src/atlas/market/      Phase 2  Market State Engine (regime ≠ state ≠ setup)
src/atlas/opportunity/ Phase 2  setup detectors, lifecycle, LONG/SHORT searched independently
src/atlas/quant/       Phase 3  statsmodels models, P(target before stop), Monte Carlo, QES, EV
src/atlas/instruments/ Phase 4  instrument search (cash→futures→options→spreads), cost model
src/atlas/execution/   Phase 5  ExecutionPort, ManualPaperAdapter (TradingView = human venue), order FSM, reconciliation
src/atlas/monitor/     Phase 6  position health GREEN/YELLOW/RED, event detector/filter, kill switch runtime
src/atlas/learning/    Phase 7  journal, prediction ledger, Brier/calibration, strategy scorecards
src/atlas/ui/          Phase 8  cockpit (FastAPI + static frontend) reading backend state only
```

Every external dependency (market data, execution venue, LLM reasoning) sits behind a
port (Python `Protocol`) and is injected. Deterministic engines never call an LLM.

## Event store

* Table `events`: `seq`, `event_id`, `idempotency_key` (UNIQUE), `type`, `priority`
  (P0–P3), `ts_utc`, `payload` (canonical JSON), `config_version`, `config_hash`,
  `atlas_version`, `prev_hash`, `hash`.
* `hash = sha256(prev_hash + canonical(event body))`. Any edit breaks the chain.
* SQLite triggers abort `UPDATE`/`DELETE` on `events`.
* Table `snapshots`: projection state at a given `seq` + hash of that state. On restart
  the store is replayed and compared against the latest snapshot.

## Phase 1 decision path

```
synthetic TradeCandidate (JSON)
 → CANDIDATE_RECEIVED (idempotent on candidate_id)
 → RiskEngine.evaluate(candidate, RiskState, instrument spec, clock)
     gates: kill switch · runtime health · risk mode · candidate structure · data freshness/provenance
            · instrument verification · sizing (floor) · min-lot vs budget · outlay/margin vs capital
            · daily-loss headroom · max positions · correlation cluster budget
 → RISK_DECISION {RISK_PASS + sizing | VETO + reasons}
 → snapshot
```
