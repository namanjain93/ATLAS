# ATLAS Agent Architecture

## Principle

Use a small hierarchy of deterministic engines plus specialized reasoning components. Do not create dozens of autonomous LLM agents.

## Components

### Orchestrator

Responsibilities:

- event routing
- workflow control
- state transitions
- calling only relevant components
- enforcing priority

It does not override Risk Engine.

### Market State Engine

Answers: What environment are we in?

### Opportunity Engine

Answers: Is there a candidate setup?

### Analysis Council

Specialists:

- Technical
- Derivatives
- Macro/Global
- News/Sentiment
- Strategy

Specialists produce evidence.

### Bull/Bear Council

Produces explicit opposing cases.

### Quant Engine

Produces statistical/model evidence.

### Instrument Engine

Finds the best executable structure for the account.

### Risk Engine

Highest authority after kill switch.

### Decision Engine

Combines evidence and produces TRADE / WATCH / NO TRADE.

### Monitor

Tracks open positions.

### Journal

Records all decisions and outcomes.

### Calibration Engine

Compares predictions with realized outcomes.

## Invocation policy

Morning:

- global/macro
- market state
- news
- opportunity

Candidate:

- technical
- derivatives
- strategy

Serious candidate:

- all relevant specialists
- bull/bear
- quant
- risk

Open position:

- market state
- technical
- derivatives
- news
- risk

Avoid full LLM regeneration every minute.
