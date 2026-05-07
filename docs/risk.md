# Risk Notes

## $100 Account Feasibility

With $100, the bot must prioritize survival over trade frequency. A single $0.50
option contract costs roughly $50 before slippage and fees, which is already
half the account. The default config caps per-trade risk to 10 percent, so most
contracts will still be rejected until risk limits are raised or account equity
grows.

This is intentional. A system that accepts most $100-account option trades is
probably accepting unrealistic loss concentration.

## Wheel Strategy

The wheel is implemented but heavily gated. Cash-secured puts require assignment
buying power:

```text
strike * 100 - premium received
```

A $5 strike already implies about $500 of assignment notional. Most wheel trades
therefore reject for a $100 account.

## Long Options

Long calls and puts are defined-risk because the premium is the max loss. They
still face:

- fast theta decay
- wide bid/ask spreads
- poor fills
- IV crush
- stop-loss gap risk
- high variance

## Vertical Spreads

Debit verticals define risk through net debit, but require:

- options level 3
- multi-leg order support
- sufficient options buying power
- synchronized leg liquidity
- realistic leg-pricing assumptions in backtests

## Backtesting Risks

The backtester includes slippage and rejects missing Alpaca data. It still cannot
eliminate:

- survivorship bias
- stale or missing option chains
- optimistic fills
- spread widening during volatility events
- overfitting
- unmodeled assignment and exercise behavior outside wheel simulations
