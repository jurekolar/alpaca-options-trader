"""Core domain models used across strategies, risk, execution, and backtests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class OptionRight(StrEnum):
    CALL = "call"
    PUT = "put"


class StrategyKind(StrEnum):
    WHEEL = "wheel"
    LONG_OPTIONS = "long_options"
    VERTICAL_SPREADS = "vertical_spreads"
    ADVANCED_SMALL_ACCOUNT = "advanced_small_account"


class TradeAction(StrEnum):
    BUY_TO_OPEN = "buy_to_open"
    SELL_TO_OPEN = "sell_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_CLOSE = "sell_to_close"


class RejectionReason(StrEnum):
    LIVE_TRADING_NOT_ALLOWED = "live_trading_not_allowed"
    OPTIONS_NOT_APPROVED = "options_not_approved"
    OPTIONS_LEVEL_TOO_LOW = "options_level_too_low"
    MISSING_MULTI_LEG_SUPPORT = "missing_multi_leg_support"
    MARKET_DATA_UNAVAILABLE = "market_data_unavailable"
    HISTORICAL_DATA_UNAVAILABLE = "historical_data_unavailable"
    INSUFFICIENT_BUYING_POWER = "insufficient_buying_power"
    ASSIGNMENT_RISK_TOO_LARGE = "assignment_risk_too_large"
    NAKED_SHORT_NOT_ALLOWED = "naked_short_not_allowed"
    EXCESSIVE_SPREAD = "excessive_spread"
    ILLIQUID_CONTRACT = "illiquid_contract"
    OVERSIZED_POSITION = "oversized_position"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    MAX_POSITIONS = "max_positions"
    MAX_TRADES_PER_DAY = "max_trades_per_day"
    EARNINGS_RISK = "earnings_risk"
    ZERO_DTE_DISABLED = "zero_dte_disabled"
    LOW_SCORE = "low_score"
    INVALID_STRATEGY = "invalid_strategy"


@dataclass(frozen=True)
class Greeks:
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float
    bid_size: int = 0
    ask_size: int = 0
    timestamp: datetime | None = None

    @property
    def mid(self) -> float:
        if self.bid <= 0:
            return self.ask
        if self.ask <= 0:
            return self.bid
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)

    @property
    def spread_pct_of_mid(self) -> float:
        mid = self.mid
        if mid <= 0:
            return float("inf")
        return self.spread / mid


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    underlying_symbol: str
    expiration_date: date
    strike_price: float
    right: OptionRight
    quote: Quote | None = None
    greeks: Greeks = field(default_factory=Greeks)
    implied_volatility: float | None = None
    open_interest: int | None = None
    volume: int | None = None
    tradable: bool = True

    def dte(self, today: date | None = None) -> int:
        today = today or date.today()
        return (self.expiration_date - today).days

    @property
    def mark(self) -> float | None:
        return self.quote.mid if self.quote else None

    @property
    def ask(self) -> float | None:
        return self.quote.ask if self.quote else None

    @property
    def bid(self) -> float | None:
        return self.quote.bid if self.quote else None

    @property
    def spread_pct(self) -> float:
        return self.quote.spread_pct_of_mid if self.quote else float("inf")


@dataclass(frozen=True)
class UnderlyingSnapshot:
    symbol: str
    price: float
    atr: float | None = None
    realized_volatility: float | None = None
    intraday_change_pct: float | None = None
    relative_volume: float | None = None
    vwap_deviation_pct: float | None = None
    halted: bool = False
    earnings_today: bool = False
    scheduled_news_risk: bool = False


@dataclass(frozen=True)
class OptionLeg:
    contract: OptionContract
    action: TradeAction
    ratio: int = 1


@dataclass
class TradeCandidate:
    strategy: StrategyKind
    underlying_symbol: str
    legs: list[OptionLeg]
    quantity: int
    max_loss: float
    expected_reward: float
    buying_power_effect: float
    score: float
    rationale: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_defined_risk(self) -> bool:
        return self.max_loss >= 0 and self.max_loss < float("inf")

    @property
    def symbols(self) -> list[str]:
        return [leg.contract.symbol for leg in self.legs]


@dataclass(frozen=True)
class TradeRejection:
    reason: RejectionReason
    message: str
    candidate: TradeCandidate | None = None


@dataclass
class TradeDecision:
    accepted: list[TradeCandidate] = field(default_factory=list)
    rejected: list[TradeRejection] = field(default_factory=list)

    def add_rejection(
        self,
        reason: RejectionReason,
        message: str,
        candidate: TradeCandidate | None = None,
    ) -> None:
        self.rejected.append(TradeRejection(reason=reason, message=message, candidate=candidate))


@dataclass(frozen=True)
class AccountState:
    equity: float
    cash: float
    buying_power: float
    options_buying_power: float | None = None
    paper: bool = True
    options_approved: bool = False
    options_trading_level: int = 0
    multi_leg_supported: bool = False
    market_data_entitled: bool = False
    day_trade_count: int = 0

    @property
    def effective_options_buying_power(self) -> float:
        return self.options_buying_power if self.options_buying_power is not None else self.buying_power


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    market_value: float
    average_entry_price: float
    asset_class: str = "option"
    side: str | None = None


@dataclass(frozen=True)
class OptionBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    bid: float | None = None
    ask: float | None = None

    @property
    def executable_mid(self) -> float:
        if self.bid is not None and self.ask is not None and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.close

