"""Universe research helpers.

The default list favors underlyings with consistently active listed options,
intraday movement, and enough strikes for cheap defined-risk setups. The live
Alpaca scan/backtest still decides which symbols are usable on a given day.
"""

from __future__ import annotations

from dataclasses import dataclass

from options_trader.backtesting.engine import BacktestResult
from options_trader.domain import StrategyKind, TradeAction, TradeCandidate


DEFAULT_RESEARCH_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "SMH",
    "XLK",
    "XLF",
    "XLE",
    "TLT",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMD",
    "TSLA",
    "META",
    "AMZN",
    "GOOGL",
    "NFLX",
    "AVGO",
    "QCOM",
    "MU",
    "INTC",
    "PLTR",
    "COIN",
    "MSTR",
    "SMCI",
    "HOOD",
    "UBER",
    "SOFI",
    "TQQQ",
    "SQQQ",
    "SOXL",
]


@dataclass(frozen=True)
class CandidateBacktest:
    strategy: StrategyKind
    symbols: list[str]
    result: BacktestResult | None = None
    error: str | None = None

    @property
    def pnl(self) -> float | None:
        if self.result is None:
            return None
        return round(self.result.ending_cash - self.result.starting_cash, 2)

    @property
    def profitable(self) -> bool | None:
        pnl = self.pnl
        return None if pnl is None else pnl > 0


def research_symbol_universe(
    configured_symbols: list[str],
    extra_symbols: list[str] | None = None,
) -> list[str]:
    """Return a de-duplicated research universe, preserving priority order."""
    return _unique_symbols(
        configured_symbols,
        DEFAULT_RESEARCH_UNIVERSE,
        extra_symbols or [],
    )


def backtestable_candidate_symbols(candidate: TradeCandidate) -> list[str]:
    """Return option symbols needed to backtest a generated candidate."""
    if candidate.strategy == StrategyKind.LONG_OPTIONS and len(candidate.legs) == 1:
        return [candidate.legs[0].contract.symbol]
    if candidate.strategy != StrategyKind.VERTICAL_SPREADS or len(candidate.legs) != 2:
        return []

    long_leg = next(
        (leg.contract.symbol for leg in candidate.legs if leg.action == TradeAction.BUY_TO_OPEN),
        None,
    )
    short_leg = next(
        (leg.contract.symbol for leg in candidate.legs if leg.action == TradeAction.SELL_TO_OPEN),
        None,
    )
    if not long_leg or not short_leg:
        return []
    return [long_leg, short_leg]


def _unique_symbols(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    symbols: list[str] = []
    for group in groups:
        for raw_symbol in group:
            symbol = raw_symbol.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            symbols.append(symbol)
    return symbols
