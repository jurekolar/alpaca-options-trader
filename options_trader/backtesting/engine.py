"""Dependency-free options backtesting engine.

The engine consumes Alpaca historical option bars through an injected data source.
It never creates synthetic prices if Alpaca returns no historical options data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from options_trader.config.models import BotConfig
from options_trader.domain import OptionBar, StrategyKind
from options_trader.exceptions import HistoricalDataUnavailableError


class HistoricalOptionsDataSource(Protocol):
    def get_historical_bars(
        self,
        option_symbols: list[str],
        start: datetime,
        end: datetime,
        limit: int | None = None,
    ) -> dict[str, list[OptionBar]]:
        ...


@dataclass(frozen=True)
class SimulatedTrade:
    symbol: str
    strategy: StrategyKind
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    max_loss: float
    reason: str

    @property
    def duration_minutes(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds() / 60.0


@dataclass
class BacktestResult:
    starting_cash: float
    ending_cash: float
    trades: list[SimulatedTrade] = field(default_factory=list)
    rejected_trade_count: int = 0
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class BacktestEngine:
    def __init__(self, config: BotConfig, data_source: HistoricalOptionsDataSource) -> None:
        self.config = config
        self.data_source = data_source

    def run_long_option_backtest(
        self,
        option_symbols: list[str],
        start: datetime,
        end: datetime,
    ) -> BacktestResult:
        bars_by_symbol = self.data_source.get_historical_bars(option_symbols, start, end)
        if not bars_by_symbol or not any(bars_by_symbol.values()):
            raise HistoricalDataUnavailableError(
                "Alpaca historical option bars are unavailable for "
                f"{', '.join(option_symbols)} between {start.isoformat()} and {end.isoformat()}; "
                "backtest aborted"
            )

        cash = self.config.risk.starting_cash
        result = BacktestResult(starting_cash=cash, ending_cash=cash)
        for symbol, bars in bars_by_symbol.items():
            if len(bars) < 2:
                result.rejected_trade_count += 1
                result.notes.append(f"{symbol}: rejected, fewer than two historical bars")
                continue
            trade = self._simulate_single_long_option(symbol, bars, cash)
            if trade is None:
                result.rejected_trade_count += 1
                continue
            cash += trade.pnl
            result.trades.append(trade)
            result.equity_curve.append((trade.exit_time, cash))
            if cash <= 0:
                result.notes.append("cash depleted; stopping backtest")
                break
        result.ending_cash = round(cash, 2)
        return result

    def run_vertical_spread_backtest(
        self,
        long_symbol: str,
        short_symbol: str,
        start: datetime,
        end: datetime,
    ) -> BacktestResult:
        bars_by_symbol = self.data_source.get_historical_bars(
            [long_symbol, short_symbol],
            start,
            end,
        )
        long_bars = bars_by_symbol.get(long_symbol, [])
        short_bars = bars_by_symbol.get(short_symbol, [])
        if not long_bars or not short_bars:
            missing = []
            if not long_bars:
                missing.append(long_symbol)
            if not short_bars:
                missing.append(short_symbol)
            raise HistoricalDataUnavailableError(
                "Alpaca historical option bars are unavailable for "
                f"{', '.join(missing)} between {start.isoformat()} and {end.isoformat()}"
            )
        paired = list(zip(long_bars, short_bars, strict=False))
        if len(paired) < 2:
            raise HistoricalDataUnavailableError(
                "Not enough synchronized option bars for spread backtest"
            )

        cash = self.config.risk.starting_cash
        entry_long, entry_short = paired[0]
        entry_debit = max(
            0.01,
            (entry_long.executable_mid - entry_short.executable_mid)
            * (1.0 + self.config.backtest.entry_slippage_pct),
        )
        max_loss = entry_debit * 100
        if max_loss > cash or max_loss > cash * self.config.risk.max_account_risk_per_trade_pct:
            return BacktestResult(
                starting_cash=cash,
                ending_cash=cash,
                rejected_trade_count=1,
                notes=["spread rejected by buying power or risk-per-trade limit"],
            )

        stop = entry_debit * 0.50
        take_profit = entry_debit * (1.0 + self.config.strategies.long_take_profit_pct)
        exit_long, exit_short = paired[-1]
        exit_debit = max(0.0, exit_long.executable_mid - exit_short.executable_mid)
        reason = "end_of_period"
        for long_bar, short_bar in paired[1:]:
            spread_mid = max(0.0, long_bar.executable_mid - short_bar.executable_mid)
            if spread_mid <= stop:
                exit_long, exit_short = long_bar, short_bar
                exit_debit = stop * (1.0 - self.config.backtest.exit_slippage_pct)
                reason = "stop_loss"
                break
            if spread_mid >= take_profit:
                exit_long, exit_short = long_bar, short_bar
                exit_debit = take_profit * (1.0 - self.config.backtest.exit_slippage_pct)
                reason = "take_profit"
                break
        else:
            exit_debit *= 1.0 - self.config.backtest.exit_slippage_pct
            if self.config.backtest.end_of_day_liquidation:
                reason = "end_of_day_liquidation"

        fees = 2 * (
            self.config.backtest.commission_per_contract + self.config.backtest.fees_per_contract
        )
        pnl = (exit_debit - entry_debit) * 100 - fees * 2
        trade = SimulatedTrade(
            symbol=f"{long_symbol}/{short_symbol}",
            strategy=StrategyKind.VERTICAL_SPREADS,
            entry_time=entry_long.timestamp,
            exit_time=exit_long.timestamp,
            entry_price=round(entry_debit, 4),
            exit_price=round(exit_debit, 4),
            quantity=1,
            pnl=round(pnl, 2),
            max_loss=round(max_loss, 2),
            reason=reason,
        )
        ending_cash = round(cash + trade.pnl, 2)
        return BacktestResult(
            starting_cash=cash,
            ending_cash=ending_cash,
            trades=[trade],
            equity_curve=[(trade.exit_time, ending_cash)],
        )

    def _simulate_single_long_option(
        self,
        symbol: str,
        bars: list[OptionBar],
        cash: float,
    ) -> SimulatedTrade | None:
        entry_bar = bars[0]
        entry = entry_bar.executable_mid * (1.0 + self.config.backtest.entry_slippage_pct)
        max_loss = entry * 100
        if entry <= 0 or max_loss > cash:
            return None
        risk_cap = cash * self.config.risk.max_account_risk_per_trade_pct
        if max_loss > risk_cap:
            return None

        stop = entry * (1.0 - self.config.strategies.long_stop_loss_pct)
        take_profit = entry * (1.0 + self.config.strategies.long_take_profit_pct)
        exit_bar = bars[-1]
        reason = "end_of_period"
        exit_price = exit_bar.executable_mid
        for bar in bars[1:]:
            if bar.low <= stop:
                exit_bar = bar
                exit_price = stop * (1.0 - self.config.backtest.exit_slippage_pct)
                reason = "stop_loss"
                break
            if bar.high >= take_profit:
                exit_bar = bar
                exit_price = take_profit * (1.0 - self.config.backtest.exit_slippage_pct)
                reason = "take_profit"
                break
        else:
            exit_price = exit_bar.executable_mid * (1.0 - self.config.backtest.exit_slippage_pct)
            if self.config.backtest.end_of_day_liquidation:
                reason = "end_of_day_liquidation"

        fees = self.config.backtest.commission_per_contract + self.config.backtest.fees_per_contract
        pnl = (exit_price - entry) * 100 - fees * 2
        return SimulatedTrade(
            symbol=symbol,
            strategy=StrategyKind.LONG_OPTIONS,
            entry_time=entry_bar.timestamp,
            exit_time=exit_bar.timestamp,
            entry_price=round(entry, 4),
            exit_price=round(exit_price, 4),
            quantity=1,
            pnl=round(pnl, 2),
            max_loss=round(max_loss, 2),
            reason=reason,
        )
