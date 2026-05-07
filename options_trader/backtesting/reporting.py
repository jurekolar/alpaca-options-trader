"""Backtest performance metrics."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev

from options_trader.backtesting.engine import BacktestResult


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    cagr: float | None
    max_drawdown: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    expectancy: float
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float | None
    assignment_rate: float
    rejected_trade_count: int
    largest_loss: float
    largest_win: float
    average_trade_duration_minutes: float
    risk_adjusted_return: float | None


def compute_metrics(result: BacktestResult) -> PerformanceMetrics:
    trades = result.trades
    pnl = [trade.pnl for trade in trades]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    total_return = (
        (result.ending_cash / result.starting_cash) - 1.0 if result.starting_cash > 0 else 0.0
    )
    max_dd = _max_drawdown([equity for _, equity in result.equity_curve], result.starting_cash)
    win_rate = len(wins) / len(trades) if trades else 0.0
    average_win = mean(wins) if wins else 0.0
    average_loss = mean(losses) if losses else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    expectancy = mean(pnl) if pnl else 0.0
    durations = [trade.duration_minutes for trade in trades]
    returns = [
        trade.pnl / max(trade.max_loss, 1.0)
        for trade in trades
    ]
    sharpe = _sharpe(returns)
    sortino = _sortino(returns)
    risk_adjusted = total_return / max_dd if max_dd > 0 else None
    return PerformanceMetrics(
        total_return=round(total_return, 4),
        cagr=None,
        max_drawdown=round(max_dd, 4),
        sharpe_ratio=None if sharpe is None else round(sharpe, 4),
        sortino_ratio=None if sortino is None else round(sortino, 4),
        expectancy=round(expectancy, 2),
        win_rate=round(win_rate, 4),
        average_win=round(average_win, 2),
        average_loss=round(average_loss, 2),
        profit_factor=None if profit_factor is None else round(profit_factor, 4),
        assignment_rate=0.0,
        rejected_trade_count=result.rejected_trade_count,
        largest_loss=round(min(pnl), 2) if pnl else 0.0,
        largest_win=round(max(pnl), 2) if pnl else 0.0,
        average_trade_duration_minutes=round(mean(durations), 2) if durations else 0.0,
        risk_adjusted_return=None if risk_adjusted is None else round(risk_adjusted, 4),
    )


def _max_drawdown(equity_curve: list[float], starting_cash: float) -> float:
    if not equity_curve:
        return 0.0
    peak = starting_cash
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown


def _sharpe(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    stdev = pstdev(returns)
    if stdev == 0:
        return None
    return mean(returns) / stdev * sqrt(len(returns))


def _sortino(returns: list[float]) -> float | None:
    downside = [value for value in returns if value < 0]
    if len(downside) < 2:
        return None
    downside_stdev = pstdev(downside)
    if downside_stdev == 0:
        return None
    return mean(returns) / downside_stdev * sqrt(len(returns))

