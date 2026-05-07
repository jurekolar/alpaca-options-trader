# Alpaca Options Trader

Small-account intraday options trading framework for Alpaca. It defaults to paper
trading, starts from a $100 capital assumption, and favors defined-risk trades.

This project is not a profitability system. It is a guarded trading framework
that makes risk, account eligibility, liquidity, and data availability explicit.

## Reality Check

- A traditional wheel is usually not practical with $100 because a cash-secured
  put requires enough buying power to purchase 100 shares if assigned.
- Long calls and long puts are the default small-account strategy because max
  loss is the premium paid.
- Debit vertical spreads are supported only when the account has sufficient
  options trading level and multi-leg support.
- 0DTE/1DTE aggressive tactics are disabled by default. 1DTE is configurable;
  0DTE requires explicit opt-in.
- The bot never permits naked short options unless explicitly enabled in config.
- Backtests use Alpaca historical option data only. If data is unavailable, the
  backtest fails instead of falling back to synthetic prices.

## Architecture

```text
cli.py
config/
options_trader/
  alpaca/
    client.py
    execution.py
    market_data.py
  backtesting/
    engine.py
    reporting.py
  config/
    loader.py
    models.py
  risk/
    limits.py
    sizing.py
  signals/
    options.py
    scoring.py
    technical.py
  strategies/
    wheel.py
    long_options.py
    vertical_spreads.py
  universe/
    scanner.py
tests/
docs/
reports/
```

The Alpaca integration is nested under `options_trader.alpaca` so it does not
shadow the official `alpaca` package from `alpaca-py`.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Set Alpaca credentials:

```bash
export ALPACA_API_KEY_ID="your-key"
export ALPACA_SECRET_KEY="your-secret"
```

`APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` are also accepted.

By default, intraday stock bars use Alpaca's `iex` feed so accounts without
recent SIP data entitlement can still run scans. If your account has SIP access,
set this in TOML:

```toml
[market_data]
stock_feed = "sip"
```

Historical option bars default to a 16-minute delay so accounts without Algo
Trader Plus do not request the latest real-time OPRA window. Set this to `0`
only if the account has that subscription:

```toml
[market_data]
option_bars_delay_minutes = 0
```

## Commands

```bash
python cli.py status
python cli.py scan
python cli.py research-universe --backtest-top 5
python cli.py paper-trade --dry-run
python cli.py paper-trade
python cli.py backtest --strategy long_options --option-symbol SPY260508C00500000
python cli.py backtest --strategy vertical_spreads --long-symbol SPY260508C00500000 --short-symbol SPY260508C00501000
python cli.py report --path reports/latest_backtest.md
python cli.py close-position SPY260508C00500000 --qty 1
```

Live trading is blocked unless all three gates pass:

```bash
export ALLOW_LIVE_TRADING=true
python cli.py live-trade --i-understand-this-can-lose-money
```

Also set this in TOML:

```toml
[execution]
live_trading_enabled = true
```

## Strategies

- `long_options`: Intraday momentum or volatility-breakout long calls/puts.
  Defined risk; default small-account strategy.
- `vertical_spreads`: Debit verticals with explicit long/short legs and max
  loss equal to debit paid. Requires multi-leg support and options level 3.
- `wheel`: Cash-secured puts and covered calls. Cash-secured puts are emitted
  only when buying power supports assignment risk plus configured buffer.

## Universe Research

The default configs start from a broader liquid-options basket, then
`max_symbols_per_scan` keeps only the top-ranked names for the current session.
Use the research command before changing the static universe:

```bash
python cli.py research-universe --backtest-top 5
```

It scans the configured symbols plus the built-in research list, generates
trade candidates with the normal risk gates, and backtests the top accepted
long-option or debit-spread candidates when Alpaca historical option bars are
available. The report is saved to `reports/universe_research.md`.

## Risk Controls

Global controls:

- max account risk per trade
- max daily loss
- max drawdown
- max open positions
- max trades per day
- max position notional

Execution controls:

- limit orders by default
- slippage tolerance
- excessive spread rejection
- illiquid contract rejection
- buying-power rejection
- no naked short options by default
- no live trading without all hard gates

## Backtesting

The backtester requires real Alpaca historical option bars. It calculates:

- total return
- max drawdown
- Sharpe and Sortino where enough trades exist
- expectancy
- win rate
- average win/loss
- profit factor
- assignment rate placeholder
- rejected trade count
- largest win/loss
- average trade duration
- risk-adjusted return

If Alpaca has no historical options data for a requested contract and period, the
run fails clearly.

By default, backtest dates are `auto`: the CLI uses the supplied OCC option
symbols to choose a recent lookback window, capped at expiration for expired
contracts and delayed by `market_data.option_bars_delay_minutes` for current
contracts. Override the window when needed:

```bash
python cli.py backtest \
  --strategy long_options \
  --option-symbol SPY260508C00500000 \
  --start 2026-05-06 \
  --end 2026-05-07
```

## Troubleshooting

- `Missing Alpaca credentials`: export Alpaca API keys before running live data
  commands.
- `subscription does not permit querying recent SIP data`: keep
  `[market_data] stock_feed = "iex"` for non-SIP accounts, or switch to `sip`
  only after adding the required Alpaca market data subscription.
- `OPRA agreement is not signed`: Alpaca can return this when a historical
  option bars request includes the latest 15 minutes and the account lacks Algo
  Trader Plus. Keep `market_data.option_bars_delay_minutes = 16`, omit `--end`,
  or use an older explicit end time.
- `options market data entitlement could not be verified`: your account likely
  lacks option market data access, or the probe request failed.
- `options trading level too low`: check `python cli.py status`. Long options
  require level 2, spreads require level 3 in this framework.
- `backtest requires --option-symbol`: historical option tests must use concrete
  OCC option contract symbols.
- `Live trading blocked`: config, CLI acknowledgement, and environment variable
  must all be enabled.

## Disclosures

Options can expire worthless. Intraday option trading has severe slippage,
spread, liquidity, and timing risks. Small accounts are especially vulnerable to
position concentration and commission/fee drag. Backtests can suffer from
survivorship bias, stale chains, overfitting, and optimistic fill assumptions.
Nothing in this project guarantees returns.
