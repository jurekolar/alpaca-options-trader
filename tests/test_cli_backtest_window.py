from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
import unittest

from cli import _resolve_backtest_window
from options_trader.config.models import BacktestConfig, BotConfig, MarketDataConfig
from options_trader.domain import StrategyKind


def long_option_args(symbol: str, start: str | None = None, end: str | None = None) -> Namespace:
    return Namespace(
        strategy=StrategyKind.LONG_OPTIONS.value,
        option_symbol=[symbol],
        long_symbol=None,
        short_symbol=None,
        start=start,
        end=end,
    )


class CliBacktestWindowTests(unittest.TestCase):
    def test_auto_window_respects_delayed_option_bars_for_current_contract(self) -> None:
        now = datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc)
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5),
            market_data=MarketDataConfig(option_bars_delay_minutes=16),
        )

        start, end = _resolve_backtest_window(
            long_option_args("SPY260508C00500000"),
            config,
            ["SPY260508C00500000"],
            now=now,
        )

        self.assertEqual(end, datetime(2026, 5, 7, 19, 44, tzinfo=timezone.utc))
        self.assertEqual(start, datetime(2026, 5, 2, 19, 44, tzinfo=timezone.utc))

    def test_auto_window_caps_expired_contract_at_expiration(self) -> None:
        now = datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc)
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5),
            market_data=MarketDataConfig(option_bars_delay_minutes=16),
        )

        start, end = _resolve_backtest_window(
            long_option_args("SPY260501C00500000"),
            config,
            ["SPY260501C00500000"],
            now=now,
        )

        self.assertEqual(end, datetime(2026, 5, 2, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(start, datetime(2026, 4, 27, 0, 0, tzinfo=timezone.utc))

    def test_explicit_historical_end_date_includes_the_full_date(self) -> None:
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5),
            market_data=MarketDataConfig(option_bars_delay_minutes=16),
        )

        start, end = _resolve_backtest_window(
            long_option_args(
                "SPY260508C00500000",
                start="2026-05-06",
                end="2026-05-07",
            ),
            config,
            ["SPY260508C00500000"],
            now=datetime(2026, 5, 9, 20, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(start, datetime(2026, 5, 6, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc))

    def test_explicit_recent_end_date_is_capped_to_delayed_option_bars(self) -> None:
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5),
            market_data=MarketDataConfig(option_bars_delay_minutes=16),
        )

        start, end = _resolve_backtest_window(
            long_option_args(
                "SPY260508C00500000",
                start="2026-05-06",
                end="2026-05-07",
            ),
            config,
            ["SPY260508C00500000"],
            now=datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(start, datetime(2026, 5, 6, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 5, 7, 19, 44, tzinfo=timezone.utc))

    def test_algo_trader_plus_can_disable_option_bar_delay(self) -> None:
        now = datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc)
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5),
            market_data=MarketDataConfig(option_bars_delay_minutes=0),
        )

        _start, end = _resolve_backtest_window(
            long_option_args("SPY260508C00500000"),
            config,
            ["SPY260508C00500000"],
            now=now,
        )

        self.assertEqual(end, now)


if __name__ == "__main__":
    unittest.main()
