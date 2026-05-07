# Example Backtest Report

This file is illustrative only. Real reports are written by:

```bash
python cli.py backtest --strategy long_options --option-symbol SPY260508C00500000
```

The backtester requires Alpaca historical option bars and will fail if they are
unavailable. It does not synthesize prices.

Expected sections:

- starting and ending cash
- total return
- max drawdown
- Sharpe and Sortino where enough trades exist
- expectancy
- win rate
- average win/loss
- profit factor
- rejected trade count
- largest win/loss
- average trade duration
- trade list
- notes

