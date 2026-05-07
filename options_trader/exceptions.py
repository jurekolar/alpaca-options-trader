"""Project-specific exceptions with clear operational failure modes."""

from __future__ import annotations


class OptionsTraderError(Exception):
    """Base exception for expected bot failures."""


class MissingCredentialsError(OptionsTraderError):
    """Raised when Alpaca API credentials are required but missing."""


class LiveTradingBlockedError(OptionsTraderError):
    """Raised when live trading is requested without every required safety gate."""


class CapabilityError(OptionsTraderError):
    """Raised when an Alpaca account is not eligible for a requested strategy."""


class MarketDataUnavailableError(OptionsTraderError):
    """Raised when live or historical Alpaca market data cannot be accessed."""


class HistoricalDataUnavailableError(MarketDataUnavailableError):
    """Raised when required historical options data is unavailable."""


class RiskLimitError(OptionsTraderError):
    """Raised when a candidate violates configured risk constraints."""

