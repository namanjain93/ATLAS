# Market State Engine v2.0

## Required dimensions

### Trend

5m, 15m, 1H, 4H, Daily.

Explicitly record conflicts.

### Structure

- trend
- range
- compression
- breakout
- breakdown
- reversal
- failed breakout
- failed breakdown
- accumulation
- distribution

### Momentum

- price momentum
- ROC
- RSI
- MACD-type evidence
- ADX
- volume momentum
- acceleration/deceleration

Indicators are evidence, not commands.

### Volatility

Classify:

- low
- normal
- elevated
- extreme

Use ATR, realized volatility, IV, gaps, and range behavior.

### Liquidity

Assess:

- volume
- bid/ask
- option spread
- OI
- depth where available
- exit feasibility

### Breadth

Assess:

- advancing/declining
- % above moving averages
- sector participation
- highs/lows
- concentration

### Derivatives

Assess:

- futures basis
- OI/change OI
- put/call structure
- IV
- IV percentile/rank
- skew
- expiry positioning
- strike concentration
- option liquidity

### Cross-asset

Potential inputs:

- NIFTY
- BANKNIFTY
- USDINR
- crude
- gold
- Indian yields
- S&P
- Nasdaq
- Dow
- VIX
- DXY
- Asian markets

### Macro/news

Record:

- event
- impact
- horizon
- directional relevance
- confidence

News is not automatically directional.

## Output

Return a Market State Object containing timestamp, DQS, dimensions, regime, state, transitions, key levels, and risk environment.

Regime ≠ State ≠ Setup.
