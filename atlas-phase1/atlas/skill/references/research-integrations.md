# Research & Technology Guidance

## Preferred quantitative foundation

Statsmodels is a core research dependency for:

- ARIMA/ARIMAX
- VAR/VECM
- state-space
- Markov switching
- cointegration
- diagnostics

## Research-only model families

LSTM/GRU/seq2seq, ensembles, RL experiments, Monte Carlo, portfolio optimization and similar approaches may be used in a research lab.

Do not promote a model merely because it predicts historical prices.

## Repository-derived architectural ideas

Useful conceptual patterns:

- multi-agent evidence orchestration
- market data adapters
- screening
- backtesting
- broker abstractions
- event-driven workflows
- financial terminal UX

Any external repository strategy is a candidate, not proven alpha.

## TradingView

Do not assume a public standalone API for TradingView Paper Trading.

TradingView Paper Trading is an execution venue for the human-in-the-loop initial workflow.

A verified broker/execution adapter may replace this later.
