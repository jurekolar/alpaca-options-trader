from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from alpaca.data.enums import DataFeed

from options_trader.alpaca.market_data import AlpacaMarketData


class CapturingStockDataClient:
    def __init__(self) -> None:
        self.request = None

    def get_stock_bars(self, request):
        self.request = request
        return {
            "SPY": [
                SimpleNamespace(close=100.0, high=101.0, low=99.0, volume=1000),
                SimpleNamespace(close=101.0, high=102.0, low=100.0, volume=1100),
            ]
        }


class MarketDataTests(unittest.TestCase):
    def test_underlying_context_uses_iex_stock_feed_by_default(self) -> None:
        stock_client = CapturingStockDataClient()
        market_data = AlpacaMarketData(option_data_client=object(), stock_data_client=stock_client)
        end = datetime(2026, 5, 7, 15, 0, tzinfo=timezone.utc)

        underlying, technical = market_data.get_underlying_intraday_context(
            "SPY",
            end - timedelta(days=1),
            end,
        )

        self.assertEqual(stock_client.request.feed, DataFeed.IEX)
        self.assertEqual(underlying.price, 101.0)
        self.assertIsNotNone(technical)


if __name__ == "__main__":
    unittest.main()
