from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
import unittest

from cli import _resolve_backtest_window
from options_trader.config.models import BacktestConfig, BotConfig
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
    def test_auto_window_ends_at_now_for_current_contract(self) -> None:
        now = datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc)
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5)
        )

        start, end = _resolve_backtest_window(
            long_option_args("SPY260508C00500000"),
            config,
            ["SPY260508C00500000"],
            now=now,
        )

        self.assertEqual(end, now)
        self.assertEqual(start, datetime(2026, 5, 2, 20, 0, tzinfo=timezone.utc))

    def test_auto_window_caps_expired_contract_at_expiration(self) -> None:
        now = datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc)
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5)
        )

        start, end = _resolve_backtest_window(
            long_option_args("SPY260501C00500000"),
            config,
            ["SPY260501C00500000"],
            now=now,
        )

        self.assertEqual(end, datetime(2026, 5, 2, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(start, datetime(2026, 4, 27, 0, 0, tzinfo=timezone.utc))

    def test_explicit_end_date_includes_the_full_date(self) -> None:
        config = BotConfig(
            backtest=BacktestConfig(start="auto", end="auto", auto_lookback_days=5)
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
        self.assertEqual(end, datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
