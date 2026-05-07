"""Typed config models.

The project uses TOML to avoid runtime YAML dependencies. The models are intentionally
small and explicit so unsafe defaults are hard to miss in review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _float(value: Any, default: float) -> float:
    return default if value is None else float(value)


def _int(value: Any, default: int) -> int:
    return default if value is None else int(value)


def _bool(value: Any, default: bool) -> bool:
    return default if value is None else bool(value)


def _str(value: Any, default: str) -> str:
    return default if value is None else str(value)


def _str_list(value: Any, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    return [str(item).upper() for item in value]


@dataclass(frozen=True)
class RiskConfig:
    starting_cash: float = 100.0
    max_account_risk_per_trade_pct: float = 0.10
    max_daily_loss_pct: float = 0.08
    max_drawdown_pct: float = 0.20
    max_open_positions: int = 2
    max_trades_per_day: int = 3
    max_position_notional: float = 35.0
    allow_margin: bool = False
    allow_naked_short_options: bool = False
    emergency_exit_slippage_pct: float = 0.25

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RiskConfig":
        return cls(
            starting_cash=_float(data.get("starting_cash"), 100.0),
            max_account_risk_per_trade_pct=_float(data.get("max_account_risk_per_trade_pct"), 0.10),
            max_daily_loss_pct=_float(data.get("max_daily_loss_pct"), 0.08),
            max_drawdown_pct=_float(data.get("max_drawdown_pct"), 0.20),
            max_open_positions=_int(data.get("max_open_positions"), 2),
            max_trades_per_day=_int(data.get("max_trades_per_day"), 3),
            max_position_notional=_float(data.get("max_position_notional"), 35.0),
            allow_margin=_bool(data.get("allow_margin"), False),
            allow_naked_short_options=_bool(data.get("allow_naked_short_options"), False),
            emergency_exit_slippage_pct=_float(data.get("emergency_exit_slippage_pct"), 0.25),
        )


@dataclass(frozen=True)
class LiquidityConfig:
    min_open_interest: int = 100
    min_option_volume: int = 10
    max_bid_ask_spread_pct: float = 0.20
    min_bid: float = 0.01
    min_underlying_price: float = 1.0
    max_underlying_price: float = 550.0
    avoid_earnings: bool = True
    avoid_scheduled_news: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "LiquidityConfig":
        return cls(
            min_open_interest=_int(data.get("min_open_interest"), 100),
            min_option_volume=_int(data.get("min_option_volume"), 10),
            max_bid_ask_spread_pct=_float(data.get("max_bid_ask_spread_pct"), 0.20),
            min_bid=_float(data.get("min_bid"), 0.01),
            min_underlying_price=_float(data.get("min_underlying_price"), 1.0),
            max_underlying_price=_float(data.get("max_underlying_price"), 550.0),
            avoid_earnings=_bool(data.get("avoid_earnings"), True),
            avoid_scheduled_news=_bool(data.get("avoid_scheduled_news"), True),
        )


@dataclass(frozen=True)
class ExecutionConfig:
    paper_trading_default: bool = True
    live_trading_enabled: bool = False
    prefer_limit_orders: bool = True
    slippage_tolerance_pct: float = 0.10
    order_timeout_seconds: int = 45
    close_positions_before_eod: bool = True
    liquidation_minutes_before_close: int = 10

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ExecutionConfig":
        return cls(
            paper_trading_default=_bool(data.get("paper_trading_default"), True),
            live_trading_enabled=_bool(data.get("live_trading_enabled"), False),
            prefer_limit_orders=_bool(data.get("prefer_limit_orders"), True),
            slippage_tolerance_pct=_float(data.get("slippage_tolerance_pct"), 0.10),
            order_timeout_seconds=_int(data.get("order_timeout_seconds"), 45),
            close_positions_before_eod=_bool(data.get("close_positions_before_eod"), True),
            liquidation_minutes_before_close=_int(data.get("liquidation_minutes_before_close"), 10),
        )


@dataclass(frozen=True)
class UniverseConfig:
    symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA"])
    excluded_symbols: list[str] = field(default_factory=list)
    max_symbols_per_scan: int = 12
    max_contract_price: float = 0.35
    min_dte: int = 1
    max_dte: int = 14
    allow_zero_dte: bool = False
    allow_one_dte: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "UniverseConfig":
        return cls(
            symbols=_str_list(data.get("symbols"), ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA"]),
            excluded_symbols=_str_list(data.get("excluded_symbols"), []),
            max_symbols_per_scan=_int(data.get("max_symbols_per_scan"), 12),
            max_contract_price=_float(data.get("max_contract_price"), 0.35),
            min_dte=_int(data.get("min_dte"), 1),
            max_dte=_int(data.get("max_dte"), 14),
            allow_zero_dte=_bool(data.get("allow_zero_dte"), False),
            allow_one_dte=_bool(data.get("allow_one_dte"), True),
        )


@dataclass(frozen=True)
class StrategyConfig:
    long_options_enabled: bool = True
    wheel_enabled: bool = True
    vertical_spreads_enabled: bool = True
    advanced_small_account_enabled: bool = False
    zero_dte_enabled: bool = False
    min_options_level_long: int = 2
    min_options_level_spreads: int = 3
    min_options_level_short: int = 3
    wheel_min_cash_buffer_pct: float = 0.10
    long_stop_loss_pct: float = 0.45
    long_take_profit_pct: float = 0.80
    vertical_min_reward_risk: float = 1.0
    vertical_max_width: float = 5.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "StrategyConfig":
        return cls(
            long_options_enabled=_bool(data.get("long_options_enabled"), True),
            wheel_enabled=_bool(data.get("wheel_enabled"), True),
            vertical_spreads_enabled=_bool(data.get("vertical_spreads_enabled"), True),
            advanced_small_account_enabled=_bool(data.get("advanced_small_account_enabled"), False),
            zero_dte_enabled=_bool(data.get("zero_dte_enabled"), False),
            min_options_level_long=_int(data.get("min_options_level_long"), 2),
            min_options_level_spreads=_int(data.get("min_options_level_spreads"), 3),
            min_options_level_short=_int(data.get("min_options_level_short"), 3),
            wheel_min_cash_buffer_pct=_float(data.get("wheel_min_cash_buffer_pct"), 0.10),
            long_stop_loss_pct=_float(data.get("long_stop_loss_pct"), 0.45),
            long_take_profit_pct=_float(data.get("long_take_profit_pct"), 0.80),
            vertical_min_reward_risk=_float(data.get("vertical_min_reward_risk"), 1.0),
            vertical_max_width=_float(data.get("vertical_max_width"), 5.0),
        )


@dataclass(frozen=True)
class ScoringConfig:
    liquidity_weight: float = 0.30
    momentum_weight: float = 0.22
    volatility_weight: float = 0.16
    capital_efficiency_weight: float = 0.20
    risk_reward_weight: float = 0.12
    min_trade_score: float = 55.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ScoringConfig":
        return cls(
            liquidity_weight=_float(data.get("liquidity_weight"), 0.30),
            momentum_weight=_float(data.get("momentum_weight"), 0.22),
            volatility_weight=_float(data.get("volatility_weight"), 0.16),
            capital_efficiency_weight=_float(data.get("capital_efficiency_weight"), 0.20),
            risk_reward_weight=_float(data.get("risk_reward_weight"), 0.12),
            min_trade_score=_float(data.get("min_trade_score"), 55.0),
        )


@dataclass(frozen=True)
class BacktestConfig:
    start: str = "2024-01-01"
    end: str = "2024-03-01"
    entry_slippage_pct: float = 0.05
    exit_slippage_pct: float = 0.05
    commission_per_contract: float = 0.0
    fees_per_contract: float = 0.0
    end_of_day_liquidation: bool = True
    optimize_parameters: bool = False

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "BacktestConfig":
        return cls(
            start=str(data.get("start", "2024-01-01")),
            end=str(data.get("end", "2024-03-01")),
            entry_slippage_pct=_float(data.get("entry_slippage_pct"), 0.05),
            exit_slippage_pct=_float(data.get("exit_slippage_pct"), 0.05),
            commission_per_contract=_float(data.get("commission_per_contract"), 0.0),
            fees_per_contract=_float(data.get("fees_per_contract"), 0.0),
            end_of_day_liquidation=_bool(data.get("end_of_day_liquidation"), True),
            optimize_parameters=_bool(data.get("optimize_parameters"), False),
        )


@dataclass(frozen=True)
class MarketDataConfig:
    stock_feed: str = "iex"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "MarketDataConfig":
        stock_feed = _str(data.get("stock_feed"), "iex").lower()
        valid_feeds = {"iex", "sip", "delayed_sip", "otc", "boats", "overnight"}
        if stock_feed not in valid_feeds:
            raise ValueError(
                f"Unsupported market_data.stock_feed={stock_feed!r}; "
                f"expected one of {', '.join(sorted(valid_feeds))}"
            )
        return cls(stock_feed=stock_feed)


@dataclass(frozen=True)
class BotConfig:
    risk: RiskConfig = field(default_factory=RiskConfig)
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    strategies: StrategyConfig = field(default_factory=StrategyConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "BotConfig":
        return cls(
            risk=RiskConfig.from_mapping(data.get("risk", {})),
            liquidity=LiquidityConfig.from_mapping(data.get("liquidity", {})),
            execution=ExecutionConfig.from_mapping(data.get("execution", {})),
            universe=UniverseConfig.from_mapping(data.get("universe", {})),
            strategies=StrategyConfig.from_mapping(data.get("strategies", {})),
            scoring=ScoringConfig.from_mapping(data.get("scoring", {})),
            backtest=BacktestConfig.from_mapping(data.get("backtest", {})),
            market_data=MarketDataConfig.from_mapping(data.get("market_data", {})),
        )
