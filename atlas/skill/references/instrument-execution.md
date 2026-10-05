# Instrument & Execution Engine v2.0

## Core principle

ATLAS trades the best risk-adjusted expression of a thesis that the account can actually afford.

## Hierarchy

1. Cash/equivalent
2. Futures
3. Long options
4. Defined-risk options
5. Other approved structures

## Futures

Use exchange-defined lot sizes.

Never invent fractional lots.

If one lot exceeds the allowed risk, reject it.

## Options

Evaluate:

- premium
- max loss
- stop risk
- lot size
- IV
- Greeks
- expiry
- strike liquidity
- spread
- OI
- slippage
- gap risk

## Defined-risk structures

Preferred when they materially improve capital efficiency while preserving positive expectancy.

For verified debit spreads:

`max loss = debit × lot size`

Exact executable pricing must be verified.

## Execution states

CREATED → VALIDATED → AWAITING_APPROVAL → APPROVED → SUBMITTED → ACKNOWLEDGED → PARTIALLY_FILLED → FILLED

Terminal:

CANCELLED / REJECTED / EXPIRED

Never infer a fill from an order submission.

## Reconciliation

Compare:

- planned order
- submitted order
- acknowledged order
- actual fills
- actual position
- actual account state

Mismatch → HALT new trading until resolved.
