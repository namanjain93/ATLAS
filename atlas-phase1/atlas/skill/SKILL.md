---
name: atlas-trading-agent
description: Build, operate, validate, and extend ATLAS (Adaptive Trading & Learning Analysis System), a risk-first event-driven trading agent for Indian markets. Use when creating a trading agent, market-analysis runtime, quantitative decision engine, paper-trading workflow, risk engine, trade monitor, trading dashboard, or related research system. ATLAS supports intraday and swing trading across Indian index derivatives, selected liquid equities, and MCX commodities. It is direction-neutral, capital-aware, evidence-driven, and may return NO TRADE whenever execution, data, risk, liquidity, or expected-value constraints are not satisfied.
---

# ATLAS Trading Agent Skill

## Mission

Build ATLAS as a production-minded, risk-first trading system for Indian markets.

Prime directive:

> Maximize long-term risk-adjusted trading expectancy, not number of trades or win rate.

ATLAS must preserve capital, quantify uncertainty, prefer evidence over narrative, and treat **NO TRADE** as a valid successful decision.

This skill is implementation-oriented. Do not reproduce ATLAS as a chatbot persona. Build the underlying architecture, deterministic controls, data contracts, decision objects, state machines, tests, and user-facing decision cockpit.

## Non-negotiable principles

1. Never fabricate live prices, option quotes, Greeks, OI, news, fills, broker state, probabilities, backtest results, or model execution.
2. Risk Engine has veto authority over every strategy, model, analyst, and user-proposed trade.
3. Direction is earned by evidence. Long and short candidates must be evaluated independently.
4. Higher-timeframe regime does not force intraday direction.
5. A profitable trade can be a bad process; a losing trade can be a good process.
6. Position sizing is based on risk, not on available capital alone.
7. If the minimum tradable quantity exceeds the risk budget, reject that instrument and search for a capital-efficient alternative.
8. If execution-critical data cannot be verified at the decision timestamp, do not reconstruct or invent it.
9. User approval is required before every trade in the initial paper-trading workflow.
10. No automatic live-money execution in the initial implementation.
11. Never widen a stop merely to avoid realizing a loss.
12. Never increase position size after a loss.
13. Never average down unless explicitly defined by the strategy and independently approved by the Risk Engine.
14. Every decision must be auditable from the underlying data snapshot.
15. Persistent state, not conversation history, is the source of truth.

## Initial account constraints

Default configuration:

- Trading capital: ₹5,000
- Normal risk per trade: 2% of current trading capital
- Normal daily loss ceiling: 5% of current trading capital
- Maximum concurrent positions: 2
- User approval: required for every trade
- Execution: TradingView Paper Trading / human-in-the-loop until a verified execution adapter exists
- Intraday and swing trading enabled
- Short swing: 2–5 trading days
- Swing: 1–4 weeks

Profit allocation:

- Deduct actual trading costs first.
- From every net realized profit:
  - 30% → non-trading profit reserve
  - 70% → trading capital
- Reserve cannot be used for trading.
- Losses reduce trading capital.
- Deposits are capital, not profit.

These are configuration defaults, not assumptions to silently change.

## Initial universe

Primary:

- NIFTY 50
- BANKNIFTY
- FINNIFTY
- SENSEX
- MCX Gold
- MCX Silver
- MCX Crude Oil

Later:

- selected liquid NSE equities

Instrument selection must be capital-aware. Futures are not automatically preferred over options. Options and defined-risk structures must be considered when they provide a superior risk-adjusted expression and can be verified.

## System architecture

Implement the following logical components:

```text
ATLAS Orchestrator
├── Data Layer
├── Market State Engine
├── Opportunity Engine
├── Analysis Council
│   ├── Technical Analyst
│   ├── Derivatives Analyst
│   ├── Macro & Global Analyst
│   ├── News & Sentiment Analyst
│   └── Strategy Analyst
├── Bull/Bear Council
├── Quant Engine
├── Instrument & Execution Engine
├── Risk Engine
├── ATLAS Decision Engine
├── Continuous Position Monitor
├── Persistent State / Event Store
├── Trade Journal
├── Capital Ledger
└── Calibration & Performance Engine
```

Do not build dozens of LLM agents. Specialists provide evidence; they do not vote.

The Orchestrator is traffic control, not the primary analyst.

## Master event loop

```text
MARKET DATA
→ VALIDATE
→ MARKET STATE
→ OPPORTUNITY
→ QUANT
→ INSTRUMENT
→ RISK
→ ATLAS DECISION
→ USER APPROVAL
→ PAPER EXECUTION
→ RECONCILIATION
→ MONITOR
→ EXIT
→ JOURNAL
→ CAPITAL
→ CALIBRATION
→ RESEARCH
```

Event priorities:

- P0: emergency
- P1: critical market event
- P2: opportunity
- P3: background

P0 always preempts lower priorities.

## Decision hierarchy

```text
Kill Switch
    ↓
Risk Engine
    ↓
Data Integrity
    ↓
Portfolio Constraints
    ↓
ATLAS Decision
    ↓
Strategy
```

A lower layer cannot override a higher layer.

## Direction-neutral logic

Always evaluate:

- LONG
- SHORT
- WAIT / NO TRADE

independently.

A bearish higher-timeframe regime may still produce a valid long intraday reversal. A bullish regime may still produce a valid short breakdown.

If neither direction satisfies all gates, return NO TRADE.

## Trade qualification

A trade normally requires:

- Confidence ≥ 70
- Probability preferably ≥ 55%
- Positive expected value after estimated costs
- R:R normally ≥ 1:1.5
- Risk within configured limits
- Adequate liquidity
- No critical event conflict
- Valid entry
- Valid stop
- Valid target(s)
- Valid invalidation
- Execution-critical data verified
- Risk Engine approval

Confidence is not authorization.

Probability must never be fabricated. If evidence is insufficient, set probability to UNKNOWN and reject execution.

## Quantitative evidence

Quantitative models answer:

1. What regime are we in?
2. What outcomes are plausible?
3. What is the probability of target before stop?
4. Is expected value positive after costs?

Preferred statistical foundation:

- AR / ARIMA / ARIMAX
- VAR / VECM
- Markov switching
- state-space models
- exponential smoothing
- cointegration tests
- statistical diagnostics
- volatility/return models
- probability calibration

ML models are research evidence, not automatic production authorities.

Monte Carlo can evaluate:

- target-before-stop probability
- MAE
- MFE
- expected duration
- tail outcomes
- gap scenarios

## Three distinct quality scores

### DQS — Data Quality Score

Measures:

- freshness
- source quality
- completeness
- consistency
- timestamp integrity
- point-in-time integrity

### QES — Quantitative Evidence Score

Measures:

- model agreement
- empirical support
- sample quality
- calibration
- regime match
- data quality
- cost/liquidity robustness

### ATLAS Confidence

Measures overall trade confidence using context-dependent evidence.

Do not merge these three scores.

## Default confidence model

Initial weights:

- Market regime: 15%
- Price / technical: 20%
- Momentum / volume: 10%
- Derivatives: 15%
- Macro / global: 10%
- News / event: 10%
- R:R: 10%
- Historical evidence: 10%

Strategy-specific weighting may modify these while preserving auditability.

Confidence bands:

- 90–100: exceptional
- 80–89: high
- 70–79: good / tradable if all gates pass
- 60–69: moderate / watch
- <60: weak / no trade

## Expected value

Use:

`EV = P(win) × expected profit − P(loss) × expected loss − expected costs`

Use actual or explicitly estimated costs:

- brokerage
- exchange charges
- STT / CTT
- GST
- SEBI charges
- stamp duty
- spread
- slippage
- applicable taxes/fees

Never label a rough estimate as a measured result.

## Position sizing

```text
max_risk = current_trading_capital × allowed_risk_percent

risk_per_unit = stop_distance × unit_value
max_quantity = floor(max_risk / risk_per_unit)

lots = floor(max_quantity / contract_lot_size)
```

Always round down.

Never round risk upward.

Then adjust for:

- slippage
- fees
- margin
- liquidity
- existing exposure
- correlation
- gap risk
- option Greeks
- expiry
- spread

If one minimum lot exceeds the risk budget, reject the instrument and search another structure.

## Options

Options require analysis of:

- premium
- maximum loss
- stop risk
- lot size
- delta
- gamma
- theta
- vega
- IV
- IV rank/percentile
- expiry
- strike liquidity
- bid/ask spread
- OI
- underlying volatility
- expected move
- gap risk

Do not buy a cheap option merely because the premium is affordable.

Defined-risk spreads are first-class instruments when exact pricing and maximum loss can be verified.

For a verified debit spread:

`max_loss = net_debit × lot_size`

Do not fabricate spread pricing.

## Market State

Separate:

- Regime
- State
- Setup

Market State should include:

- multi-timeframe trend
- market structure
- momentum
- volatility
- liquidity
- breadth
- derivatives
- cross-asset context
- macro
- news/events
- key levels
- regime confidence
- state transition
- data quality

State is not a trade signal.

## Opportunity Engine

Search simultaneously for:

- trend continuation
- mean reversion
- structural reversal
- volatility setups
- derivatives setups
- swing setups

Lifecycle:

```text
IDEA
→ DETECTED
→ QUALIFYING
→ CONFIRMED
→ INSTRUMENT SEARCH
→ EV VALIDATION
→ RISK REVIEW
→ APPROVED / REJECTED
```

Setup Score default:

- Structure: 20
- Momentum: 15
- Volume: 10
- Regime alignment: 15
- Derivatives: 10
- Volatility: 10
- Cross-asset: 5
- Event/news: 5
- Historical evidence: 10

Weights can be strategy-specific.

## Instrument & Execution Engine

Core rule:

> ATLAS does not trade the market thesis; it trades the best risk-adjusted expression of that thesis that the account can actually afford.

Default hierarchy:

1. Cash/equivalent
2. Futures
3. Long options
4. Defined-risk option structures
5. Other approved instruments

Evaluate:

- maximum loss
- stop risk
- premium/outlay
- margin
- liquidity
- bid/ask
- IV
- Greeks
- expiry
- slippage
- capital efficiency
- exit feasibility

Paper execution states:

```text
CREATED
→ VALIDATED
→ AWAITING_APPROVAL
→ APPROVED
→ SUBMITTED
→ ACKNOWLEDGED
→ PARTIALLY_FILLED
→ FILLED
```

Terminal states:

- CANCELLED
- REJECTED
- EXPIRED

Never claim a fill without execution evidence.

## Risk Engine

Risk Engine can veto everything.

Controls include:

- per-trade risk
- daily loss ceiling
- drawdown
- maximum positions
- correlation
- liquidity
- event risk
- data integrity
- margin
- concentration
- gap risk
- system health
- unexpected positions
- execution anomalies

Adaptive drawdown policy:

- <5%: normal
- 5–8%: reduce risk
- 8–12%: defensive
- 12–15%: very defensive
- >15%: pause and review

Consecutive losses:

- 3: reduce risk
- 5: defensive mode

These thresholds require explicit versioning to change.

## Continuous runtime

Do not call an LLM every market tick.

Use:

```text
Market feed
→ deterministic event detection
→ event filter
→ candidate generation
→ ATLAS reasoning only when needed
```

Runtime states:

- OFFLINE
- STARTING
- READY
- SCANNING
- ANALYZING
- AWAITING_APPROVAL
- IN_POSITION
- DEFENSIVE
- HALTED
- ERROR

P0 examples:

- stop/target breach
- daily loss-limit breach
- unexpected position
- broker/account anomaly
- state corruption
- critical data failure
- kill switch

P1 examples:

- major breakout/breakdown
- extreme volatility
- macro announcement
- global shock
- major news

P2 examples:

- setup formation
- VWAP/structure interaction
- momentum + volume confirmation
- derivatives change
- swing setup

P3 examples:

- routine movement
- low-impact news
- ordinary OI changes

Use deduplication, cooldowns, and state transitions.

## Position monitoring

Position state:

- GREEN: thesis intact
- YELLOW: thesis deteriorating
- RED: thesis invalidated

Monitor:

- price
- structure
- momentum
- volatility
- derivatives
- news
- macro
- liquidity

Position Health Score is separate from entry Confidence.

Never widen stops merely to avoid loss.

Predefined trailing, partial exits, and time stops are allowed.

For options, monitor both:

- underlying thesis
- instrument behavior

Correct underlying direction does not guarantee profitable option P&L.

## Persistent state

Conversation is an interface. Persistent state is the source of truth.

Store separately:

1. Live state
2. Historical state
3. Knowledge

Source-of-truth rules:

- cash/balance → account/ledger
- positions → execution venue
- order status → execution system
- prices → market data feed
- risk limits → configuration
- trades → journal
- strategy definitions → strategy library
- ATLAS rules → Constitution

Use immutable snapshots and event sourcing for important transitions.

Recovery:

```text
restart
→ load snapshot
→ reconcile account
→ reconcile orders
→ reconcile positions
→ verify market data
→ recalculate risk
→ resume or HALT
```

Any inconsistency is a risk event.

## Learning and calibration

Separate:

- prediction quality
- decision quality
- outcome quality

Track:

- predicted probability
- realized outcome
- confidence
- QES
- DQS
- EV
- slippage
- costs
- execution quality
- regime
- strategy
- instrument

Use probability buckets and Brier score:

`BS = average((p - outcome)^2)`

Lower is better.

Strategy lifecycle:

```text
IDEA
→ FORMAL DEFINITION
→ BACKTEST
→ COST-ADJUSTED
→ WALK-FORWARD
→ OUT-OF-SAMPLE
→ PAPER
→ CALIBRATION
→ ROBUSTNESS
→ APPROVED
```

Learning may update:

- calibration
- slippage statistics
- strategy performance statistics
- regime statistics
- liquidity statistics

Learning must NOT silently change:

- Constitution
- risk limits
- profit allocation
- kill switches
- user approval requirement
- live-production promotion rules

## Trade classification

After each trade:

- A: correct thesis + good execution
- B: correct thesis + poor execution
- C: good process + unfavorable outcome
- D: bad thesis
- E: risk/process violation

Do not judge a strategy from three trades.

Suggested research sample guidance:

- <20: anecdotal
- 20–49: preliminary
- 50–99: emerging
- 100–249: meaningful research sample
- 250+: stronger evidence

These are guidance, not significance guarantees.

## Historical replay integrity

Historical replay must use only information available at the decision timestamp.

Store:

- data timestamp
- publication timestamp
- ingestion timestamp
- source
- snapshot ID
- strategy version
- ATLAS version
- risk version

No hindsight contamination.

If historical option bid/ask or point-in-time executable pricing cannot be reconstructed reliably, do not fabricate a historical trade.

## UI / decision cockpit

The preferred user experience is an interactive trading cockpit, not a prose-only report.

Minimum interface:

- account/risk summary
- market state
- opportunity card
- payoff/P&L graph
- entry / stop / targets
- probability
- confidence
- QES
- DQS
- EV
- risk amount
- R:R
- bull case
- bear case
- invalidation
- `WHY ATLAS?`
- `APPROVE TRADE`
- `REJECT`
- paper execution status
- position monitoring
- exit controls
- journal outcome

Every interactive action must correspond to a real state transition in the backend. UI must never imply that an order was actually executed unless the execution system confirms it.

## Canonical commands / intents

Support equivalent commands:

- `ATLAS MORNING`
- `ATLAS SCAN`
- `ATLAS TRADE`
- `ATLAS MONITOR`
- `ATLAS SWING`
- `ATLAS REVIEW`
- `ATLAS CAPITAL`
- `ATLAS STATUS`

Map natural-language requests to these operations where appropriate.

## Current implementation boundary

Initial production boundary:

```text
ATLAS
→ trade plan
→ user approval
→ paper execution
→ reconciliation
```

Do not assume a public TradingView Paper Trading API. Treat TradingView Paper Trading as a human-in-the-loop venue unless a verified supported integration exists.

No live broker execution until:

- execution adapter is verified
- reconciliation is verified
- risk controls are independently tested
- paper validation is complete
- explicit production approval is granted

## Build order

Implement in this order:

1. Configuration and Constitution
2. Data contracts
3. Data validation and DQS
4. Capital ledger
5. Risk Engine
6. Market State Engine
7. Opportunity Engine
8. Quant Engine
9. Instrument selection
10. Decision Engine
11. Paper execution adapter
12. Reconciliation
13. Position Monitor
14. Persistent state/event store
15. Journal
16. Calibration/performance
17. Interactive dashboard
18. Validation harness
19. Historical replay
20. Controlled paper trading

Do not start with autonomous live execution, reinforcement learning, HFT, dozens of agents, or a large data warehouse.

## Definition of done

ATLAS is not complete merely because it can generate trade ideas.

Minimum completion requires:

- deterministic risk controls
- auditable decisions
- verified data lineage
- capital-aware sizing
- paper execution reconciliation
- persistent state
- position monitoring
- journal
- calibration
- validation suite
- NO TRADE behavior
- failure recovery
- UI state consistency

Never claim profitability from architecture or scenario tests.
