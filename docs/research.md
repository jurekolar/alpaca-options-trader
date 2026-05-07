# Required Research Summary

Research was completed before implementation against the required Alpaca
resources.

## alpaca-py SDK

Relevant SDK surfaces:

- `TradingClient` is the trading boundary for account state, positions, orders,
  option contracts, clock, and account configuration.
- `TradeAccount` includes `options_buying_power`,
  `options_approved_level`, and `options_trading_level`.
- `OptionHistoricalDataClient` supports option bars, trades, latest quote,
  latest trade, snapshots, and option chains.
- `OptionChainRequest` returns option-chain snapshots with latest quote, IV, and
  Greeks by underlying symbol and filters such as expiration and strike.
- `OptionBarsRequest` retrieves historical bars for concrete option symbols.
- `OptionDataStream` is the websocket stream for real-time option data.
- Simple option orders use `LimitOrderRequest` or `MarketOrderRequest` with
  `symbol`, `qty`, `side`, `time_in_force=DAY`, and `position_intent`.
- Multi-leg option orders use `OrderClass.MLEG`, `OptionLegRequest`, `qty`, and
  `limit_price`. Positive MLEG limit price represents a debit; negative
  represents a credit.
- `PositionIntent` values are `BUY_TO_OPEN`, `BUY_TO_CLOSE`,
  `SELL_TO_OPEN`, and `SELL_TO_CLOSE`.

Implementation impact:

- Alpaca imports are isolated inside adapter methods so tests can run without
  credentials or network access.
- Account readiness is checked before strategy eligibility.
- Historical backtests fail when Alpaca options data is unavailable.
- Limit orders are preferred.

## Alpaca Options Examples

Canonical patterns inspected:

- Basic options trading uses `TradingClient`, `OptionHistoricalDataClient`,
  contract discovery, quotes, Greeks, and order request models.
- Market-data examples demonstrate option chain retrieval, snapshots, latest
  quote/trade, bars, and filtering by DTE, strike, delta, IV, open interest, and
  spread.
- Multi-leg examples demonstrate `OrderClass.MLEG` plus leg-level
  `OptionLegRequest` and `PositionIntent`.
- Strategy examples show long calls/puts, debit spreads, and data-driven
  filtering rather than blindly selecting the cheapest contract.
- Streaming examples use `OptionDataStream` for real-time quotes/trades and
  monitoring.

Implementation impact:

- The scanner normalizes option chain snapshots into internal contract models.
- Scoring includes liquidity, DTE, spread, IV/Greeks where available, and
  capital efficiency.
- Vertical spreads are represented as explicit long/short legs and require
  multi-leg support.

## alpaca/options-wheel

Reusable ideas:

- Separation of configuration, account checks, option scoring, and order
  execution.
- Wheel-specific filtering by buying power, premium, expiration, and risk.
- Clear execution flow: load config, fetch account, fetch contracts, score,
  select, place orders.

Limitations for this project:

- A $100 account generally cannot support cash-secured put assignment risk.
- Wheel strategy remains implemented but is not the default practical strategy.
- The deployment priority is long options and defined-risk debit spreads.

## Architecture Opportunities

- Keep strategy modules pure and testable.
- Put all Alpaca SDK objects behind adapter classes.
- Use TOML config for dependency-free parsing.
- Use hard risk gates before order construction.
- Report rejected trades separately from executed trades.
- Treat live trading as an exception path requiring multiple explicit gates.

## Key SDK and Product Constraints

- Options trading level matters. Alpaca account data exposes approved and active
  options levels.
- Alpaca options buying power is separate from generic buying power.
- Multi-leg support requires sufficient account capability.
- Options data entitlement must be verified by an actual options data call.
- Historical options data is only valid for concrete option symbols and periods
  available through Alpaca.
- 0DTE behavior is riskier and disabled by default.

References:

- https://github.com/alpacahq/alpaca-py
- https://github.com/alpacahq/alpaca-py/blob/master/examples/options/README.md
- https://github.com/alpacahq/options-wheel
- https://alpaca.markets/sdks/python/api_reference/data/option/historical.html
- https://alpaca.markets/sdks/python/api_reference/data/option/requests.html
- https://alpaca.markets/sdks/python/api_reference/trading/requests.html
- https://alpaca.markets/sdks/python/api_reference/trading/enums.html
- https://docs.alpaca.markets/docs/options-trading-overview

