from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from options_trader.backtesting import BacktestEngine
from options_trader.config.models import BotConfig, RiskConfig
from options_trader.domain import OptionBar
from options_trader.exceptions import HistoricalDataUnavailableError


class EmptyDataSource:
    def get_historical_bars(self, option_symbols, start, end, limit=None):
        return {}


class FakeDataSource:
    def get_historical_bars(self, option_symbols, start, end, limit=None):
        bars = {}
        for symbol in option_symbols:
            t0 = datetime(2026, 5, 7, 14, 30, tzinfo=timezone.utc)
            bars[symbol] = [
                OptionBar(symbol, t0, open=0.03, high=0.03, low=0.03, close=0.03),
                OptionBar(symbol, t0 + timedelta(minutes=1), open=0.03, high=0.08, low=0.03, close=0.07),
            ]
        return bars


class BacktestingTests(unittest.TestCase):
    def test_backtest_fails_without_alpaca_historical_data(self) -> None:
        engine = BacktestEngine(BotConfig(), EmptyDataSource())
        with self.assertRaises(HistoricalDataUnavailableError):
            engine.run_long_option_backtest(
                ["SPY260508C00100000"],
                datetime(2026, 5, 7, tzinfo=timezone.utc),
                datetime(2026, 5, 8, tzinfo=timezone.utc),
            )

    def test_long_option_backtest_executes_fake_bars(self) -> None:
        config = BotConfig(risk=RiskConfig(max_account_risk_per_trade_pct=0.10))
        engine = BacktestEngine(config, FakeDataSource())
        result = engine.run_long_option_backtest(
            ["SPY260508C00100000"],
            datetime(2026, 5, 7, tzinfo=timezone.utc),
            datetime(2026, 5, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(len(result.trades), 1)
        self.assertGreater(result.ending_cash, result.starting_cash)


if __name__ == "__main__":
    unittest.main()

