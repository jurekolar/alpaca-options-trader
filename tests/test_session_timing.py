from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

from options_trader.alpaca.session import get_market_session_timing
from options_trader.config.models import ExecutionConfig

EASTERN = ZoneInfo("America/New_York")


class FakeTradingClient:
    def __init__(
        self,
        *,
        timestamp: datetime,
        close: datetime,
        next_close: datetime | None = None,
        is_open: bool = True,
    ) -> None:
        self.clock = SimpleNamespace(
            timestamp=timestamp,
            is_open=is_open,
            next_close=next_close or close,
        )
        self.calendar = [SimpleNamespace(close=close)]

    def get_clock(self) -> SimpleNamespace:
        return self.clock

    def get_calendar(self, _filters: object) -> list[SimpleNamespace]:
        return self.calendar


class SessionTimingTests(unittest.TestCase):
    def test_outside_window_allows_entries(self) -> None:
        timing = get_market_session_timing(
            FakeTradingClient(
                timestamp=datetime(2026, 5, 7, 19, 45, tzinfo=timezone.utc),
                close=datetime(2026, 5, 7, 16, 0, tzinfo=EASTERN),
            ),
            ExecutionConfig(liquidation_minutes_before_close=10),
        )

        self.assertFalse(timing.in_liquidation_window)
        self.assertTrue(timing.entry_orders_allowed)
        self.assertEqual(timing.minutes_until_close, 15)

    def test_inside_window_blocks_entries(self) -> None:
        timing = get_market_session_timing(
            FakeTradingClient(
                timestamp=datetime(2026, 5, 7, 19, 55, tzinfo=timezone.utc),
                close=datetime(2026, 5, 7, 16, 0, tzinfo=EASTERN),
            ),
            ExecutionConfig(liquidation_minutes_before_close=10),
        )

        self.assertTrue(timing.in_liquidation_window)
        self.assertFalse(timing.entry_orders_allowed)
        self.assertEqual(timing.minutes_until_close, 5)

    def test_disabled_eod_close_leaves_entries_allowed(self) -> None:
        timing = get_market_session_timing(
            FakeTradingClient(
                timestamp=datetime(2026, 5, 7, 19, 55, tzinfo=timezone.utc),
                close=datetime(2026, 5, 7, 16, 0, tzinfo=EASTERN),
            ),
            ExecutionConfig(
                close_positions_before_eod=False,
                liquidation_minutes_before_close=10,
            ),
        )

        self.assertFalse(timing.in_liquidation_window)
        self.assertTrue(timing.entry_orders_allowed)

    def test_early_close_calendar_is_respected(self) -> None:
        timing = get_market_session_timing(
            FakeTradingClient(
                timestamp=datetime(2026, 5, 7, 16, 55, tzinfo=timezone.utc),
                close=datetime(2026, 5, 7, 13, 0),
                next_close=datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc),
            ),
            ExecutionConfig(liquidation_minutes_before_close=10),
        )

        self.assertTrue(timing.in_liquidation_window)
        self.assertEqual(timing.market_close_time, datetime(2026, 5, 7, 13, 0, tzinfo=EASTERN))
        self.assertEqual(timing.minutes_until_close, 5)


if __name__ == "__main__":
    unittest.main()
