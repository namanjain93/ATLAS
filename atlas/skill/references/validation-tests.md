# ATLAS Validation Harness

These are design/integration scenarios. Passing them is not proof of profitability.

## Core scenarios

T001 Valid LONG → trade candidate can pass.

T002 Valid SHORT → trade candidate can pass.

T003 No setup → NO TRADE.

T004 Futures exceed risk → reject futures.

T005 Affordable verified option structure → instrument can pass.

T006 Option pricing unavailable → reject execution.

T007 Execution-critical data stale → reject.

T008 Conflicting sources → flag and reduce/reject.

T009 Negative EV → reject.

T010 Confidence <70 → reject.

T011 Daily loss ceiling → block new risk.

T012 Third position → reject.

T013 Correlated second position → reduce/reject.

T014 Partial fill → recalculate exposure.

T015 Order rejected → reconcile and do not claim fill.

T016 Thesis invalidation → exit/protect.

T017 Losing streak → reduce risk.

T018 Winning streak → do not automatically increase risk.

T019 Runtime restart with open position → recover/reconcile.

T020 Unexpected position → HALT and reconcile.

T021 Duplicate order → prevent.

T022 Duplicate event → deduplicate.

T023 Stale opportunity → expire.

T024 Cheap-option trap → reject if risk/EV/structure fails.

T025 Correct underlying direction but losing option → classify instrument failure correctly.

T026 Data quality degradation → reduce confidence/restrict strategies.

T027 Major news shock → event-priority escalation.

T028 Contradictory analysts → resolve contextually, no majority voting.

T029 Probability fabrication attempt → UNKNOWN/reject.

T030 Hindsight contamination → reject contaminated replay.

T031 Profit allocation → 30/70 ledger update.

T032 Trading loss → capital decreases.

T033 Deposit → capital increases but not profit.

T034 Reserve isolation → reserve unavailable for trading.

T035 Winning trade but bad process → grade E/D as appropriate.

T036 Losing trade but good process → grade C where appropriate.

T037 Calibration deterioration → research/watch.

T038 Strategy degradation → suspend/research.

## Validation statement

A complete harness should report scenario pass/fail, evidence, state transition, and audit trail.

Never report scenario validation as live-market proof.
