# Calibration & Performance Engine v2.0

## Separate three questions

1. Was the prediction calibrated?
2. Was the decision process correct?
3. Was the outcome favorable?

## Prediction ledger

Store:

- prediction ID
- timestamp
- instrument
- direction
- P(target before stop)
- confidence
- QES
- DQS
- entry
- stop
- target
- expected duration
- regime
- strategy/version
- EV
- decision
- outcome

## Calibration

Use probability buckets:

50–54
55–59
60–64
65–69
70–74
75–79
80–84
85–89
90+

Brier score:

`BS = mean((p - outcome)^2)`

Lower is better.

## Strategy scorecard

Track:

- trades
- wins/losses
- win rate
- average win/loss
- profit factor
- expectancy
- drawdown
- calibration
- execution quality
- regime performance
- instrument performance

## Execution attribution

Separate:

theoretical P&L
→ expected execution P&L
→ actual P&L

## Trade grades

A = correct thesis + good execution

B = correct thesis + poor execution

C = good process + unfavorable outcome

D = bad thesis

E = risk/process violation

## Strategy lifecycle

IDEA → FORMAL → BACKTEST → COST-ADJUSTED → WALK-FORWARD → OOS → PAPER → CALIBRATION → ROBUSTNESS → APPROVED

No production promotion based solely on backtest.
