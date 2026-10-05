# ATLAS Interactive Decision Cockpit

## Goal

Make ATLAS feel like a trading terminal, not a chat response.

## Trade screen

Display:

- account capital
- reserve
- daily P&L
- daily loss limit
- current risk
- open positions
- runtime state
- data health
- market state
- opportunity
- instrument
- entry
- stop
- T1/T2/T3
- probability
- confidence
- QES
- DQS
- R:R
- EV
- max loss
- bull case
- bear case
- invalidation

## Visuals

At minimum:

1. payoff/P&L graph
2. risk/reward visualization

For options:

- underlying price vs option P&L where data permits
- breakeven
- max loss
- target zones
- IV/Greek notes

## Controls

- WHY ATLAS?
- APPROVE TRADE
- REJECT
- MONITOR
- EXIT
- optional predefined management controls

Controls must correspond to backend state transitions.

## State progression

SCAN
→ CANDIDATE
→ AWAITING APPROVAL
→ PAPER ORDER
→ POSITION OPEN
→ MONITOR
→ EXIT
→ JOURNAL

UI must not claim execution without confirmed execution state.
