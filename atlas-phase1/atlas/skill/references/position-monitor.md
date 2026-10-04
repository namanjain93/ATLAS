# Continuous Position Monitor v2.0

## States

GREEN:

- thesis intact
- expected management continues

YELLOW:

- thesis deteriorating
- re-evaluate EV
- consider reduction/exit according to predefined rules

RED:

- thesis invalidated
- exit/protect

## Inputs

- price
- structure
- momentum
- volatility
- derivatives
- news
- macro
- liquidity

## Position Health

Position Health Score is separate from original entry Confidence.

## Allowed management

Only predefined:

- partial exits
- trailing stops
- profit protection
- time stops
- strategy-specific exits

## Options

Monitor both underlying and option behavior.

The underlying can move correctly while an option loses due to IV, theta, spread, or Greeks.
