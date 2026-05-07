# Setup Guide

## 1. Create Environment

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## 2. Configure Credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in paper credentials first:

```dotenv
ALPACA_PAPER_API_KEY_ID="your-paper-key"
ALPACA_PAPER_SECRET_KEY="your-paper-secret"
```

Add live credentials only when you are ready to test live account readiness:

```dotenv
ALPACA_LIVE_API_KEY_ID="your-live-key"
ALPACA_LIVE_SECRET_KEY="your-live-secret"
```

The CLI defaults to paper trading. Shell exports override `.env` values when
both are set.

Scans default stock bars to Alpaca's `iex` feed to avoid recent SIP data
subscription errors. Use `[market_data] stock_feed = "sip"` only when the account
has SIP entitlement.

## 3. Verify Account

```bash
python cli.py status
```

Confirm:

- options approved is true
- options trading level is sufficient
- options buying power is available
- market data entitlement is true

## 4. Run a Scan

```bash
python cli.py scan
```

The scan ranks symbols, generates candidates, applies risk controls, and reports
accepted and rejected trades.

## 5. Paper Trade

```bash
python cli.py paper-trade --dry-run
python cli.py paper-trade
```

Use `--dry-run` first.

## 6. Research The Symbol Universe

Run a broad options-liquidity scan before expanding or pruning the TOML symbol
list:

```bash
python cli.py research-universe --backtest-top 5
```

The command writes `reports/universe_research.md` with ranked symbols,
accepted candidates, and any historical option backtests Alpaca can supply.

## 7. Backtest

Use concrete OCC option symbols. The bot will not backtest synthetic symbols.
The default config uses `start = "auto"` and `end = "auto"`, so the CLI chooses
a recent lookback window around the supplied contracts. Use `--start` and `--end`
to force a specific historical window.
Historical option bars use `market_data.option_bars_delay_minutes = 16` by
default to avoid Alpaca's latest 15-minute real-time OPRA window unless the
account has Algo Trader Plus.

```bash
python cli.py backtest --strategy long_options --option-symbol SPY260508C00500000
python cli.py backtest --strategy vertical_spreads --long-symbol SPY260508C00500000 --short-symbol SPY260508C00501000
```

## 8. Live Trading

Live trading is disabled by default. To enable, all three controls are required:

```toml
[execution]
live_trading_enabled = true
```

```bash
export ALLOW_LIVE_TRADING=true
python cli.py live-trade --i-understand-this-can-lose-money
```
