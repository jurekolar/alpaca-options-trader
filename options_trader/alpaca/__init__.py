"""Alpaca SDK integration layer.

This package intentionally lives under ``options_trader.alpaca`` so it does not
shadow the official top-level ``alpaca`` package provided by alpaca-py.
"""

from options_trader.alpaca.client import AlpacaClientFactory, AlpacaSettings
from options_trader.alpaca.execution import AlpacaExecutionClient, OrderBuilder
from options_trader.alpaca.market_data import AlpacaMarketData, parse_occ_option_symbol
from options_trader.alpaca.session import MarketSessionTiming, get_market_session_timing

__all__ = [
    "AlpacaClientFactory",
    "AlpacaExecutionClient",
    "AlpacaMarketData",
    "AlpacaSettings",
    "MarketSessionTiming",
    "OrderBuilder",
    "get_market_session_timing",
    "parse_occ_option_symbol",
]
