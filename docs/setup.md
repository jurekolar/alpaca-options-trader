# Setup Guide

## 1. Create Environment

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## 2. Configure Credentials

```bash
export ALPACA_API_KEY_ID="your-paper-key"
export ALPACA_SECRET_KEY="your-paper-secret"
```

The CLI defaults to paper trading.

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

## 6. Backtest

Use concrete OCC option symbols. The bot will not backtest synthetic symbols.
The default config uses `start = "auto"` and `end = "auto"`, so the CLI chooses
a recent lookback window around the supplied contracts. Use `--start` and `--end`
to force a specific historical window.

```bash
python cli.py backtest --strategy long_options --option-symbol SPY260508C00500000
python cli.py backtest --strategy vertical_spreads --long-symbol SPY260508C00500000 --short-symbol SPY260508C00501000
```

## 7. Live Trading

Live trading is disabled by default. To enable, all three controls are required:

```toml
[execution]
live_trading_enabled = true
```

```bash
export ALLOW_LIVE_TRADING=true
python cli.py live-trade --i-understand-this-can-lose-money
```
