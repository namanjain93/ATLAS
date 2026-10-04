# Risk Engine v2.0

## Authority

Risk Engine may veto every proposed trade.

## Formula

`max_risk = trading_capital × allowed_risk_percent`

`max_quantity = floor(max_risk / risk_per_unit)`

`lots = floor(max_quantity / lot_size)`

Round down.

## Constraints

- per-trade risk
- daily loss
- drawdown
- max positions
- correlation
- concentration
- liquidity
- event risk
- data quality
- margin
- gap risk
- system health

## Drawdown modes

<5%: normal

5–8%: reduced risk

8–12%: defensive

12–15%: very defensive

>15%: pause/review

## Losing streak

3 consecutive losses → reduce risk

5 consecutive losses → defensive

## Correlation

NIFTY and BANKNIFTY should not be treated as independent merely because they are different symbols.

Portfolio-level marginal risk must be evaluated before opening position #2.

## Hard prohibitions

Never:

- widen stop to avoid loss
- increase size after loss
- exceed risk because confidence is high
- bypass minimum lot constraints
- ignore execution-critical data failures
