# ATLAS Runtime Event Model

## Event priority

P0 Emergency
P1 Critical market
P2 Opportunity
P3 Background

## Example events

P0:

- STOP_BREACHED
- TARGET_BREACHED
- DAILY_RISK_BREACHED
- UNEXPECTED_POSITION
- ACCOUNT_MISMATCH
- STATE_CORRUPTION
- EXECUTION_ANOMALY
- DATA_FAILURE
- KILL_SWITCH

P1:

- MAJOR_BREAKOUT
- MAJOR_BREAKDOWN
- EXTREME_VOLATILITY
- MACRO_RELEASE
- GLOBAL_SHOCK
- MAJOR_NEWS

P2:

- SETUP_FORMING
- VWAP_INTERACTION
- MOMENTUM_CONFIRMATION
- VOLUME_CONFIRMATION
- DERIVATIVES_CHANGE
- SWING_SETUP

P3:

- ROUTINE_PRICE_UPDATE
- LOW_IMPACT_NEWS
- ORDINARY_OI_CHANGE

## Runtime rule

Deterministic filters wake the reasoning layer only when meaningful.

Use:

- deduplication
- cooldowns
- state transition detection
- event coalescing

Never allow repeated events to create duplicate orders.
