# Persistent State & Memory Layer v2.0

## Rule

Conversation is an interface. Persistent state is the source of truth.

## State classes

### Live state

- capital
- reserve
- risk
- positions
- orders
- daily P&L
- drawdown
- opportunities
- market state
- runtime state
- system health

### Historical state

- trades
- costs
- P&L
- strategy results
- regime results
- predictions
- calibration
- drawdowns

### Knowledge

- Constitution
- risk rules
- agent specification
- strategy definitions
- research
- validated methodologies

## Event sourcing

Important events should be immutable:

setup detected → candidate → quant validation → risk approval → user approval → order → fill → target/stop → exit → journal

## Recovery

restart → snapshot → reconcile account → reconcile orders → reconcile positions → validate market → recalculate risk → resume/HALT

## Integrity

Detect:

- duplicate orders
- missing fills
- impossible P&L
- capital mismatch
- position mismatch
- stale state
- timestamp conflicts

Any integrity failure is a risk event.

## Auto-learning boundaries

Allowed:

- calibration
- slippage
- strategy statistics
- regime statistics
- liquidity statistics

Not allowed automatically:

- Constitution changes
- risk limit changes
- profit allocation changes
- kill-switch changes
- removal of user approval
- automatic production promotion
