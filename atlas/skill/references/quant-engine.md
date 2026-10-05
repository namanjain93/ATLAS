# Quantitative Evidence Specification v1.1

## Questions

1. What regime is statistically plausible?
2. What outcomes are plausible?
3. What is P(target before stop)?
4. Is EV positive after costs?

## Models

Core:

- AR
- ARIMA
- ARIMAX
- VAR
- VECM
- Markov switching
- state-space
- exponential smoothing
- cointegration
- diagnostics

Statsmodels is the preferred initial statistical foundation.

Archived or experimental ML repositories may be used for research ideas only.

## Multivariate variables

Potential variables:

- NIFTY
- BANKNIFTY
- FINNIFTY
- SENSEX
- USDINR
- crude
- gold
- Indian yields
- global indices
- volatility indicators

## Monte Carlo

Use for:

- target/stop probability
- MAE/MFE
- duration
- tails
- gaps

## Probability

Estimate:

`P(target before stop)`

Do not substitute generic `P(price up)`.

## QES

QES measures:

- model agreement
- empirical support
- sample quality
- calibration
- regime match
- data quality
- cost robustness
- liquidity robustness

QES does not replace confidence.

## Failure controls

Reduce or reject model evidence when:

- stale data
- insufficient sample
- out-of-distribution conditions
- regime change
- poor calibration
- transaction-cost sensitivity
- liquidity deterioration
- look-ahead bias
- survivorship bias
- non-point-in-time data

Never claim a model ran unless it actually ran.
