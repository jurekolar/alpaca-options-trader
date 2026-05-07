"""Dynamic universe ranking based on liquidity, volatility, and capital efficiency."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from options_trader.config.models import BotConfig
from options_trader.domain import OptionContract, UnderlyingSnapshot
from options_trader.signals.options import liquidity_score


@dataclass(frozen=True)
class RankedSymbol:
    symbol: str
    score: float
    reasons: list[str] = field(default_factory=list)


class UniverseScanner:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def rank(
        self,
        underlyings: list[UnderlyingSnapshot],
        chains: dict[str, list[OptionContract]],
    ) -> list[RankedSymbol]:
        excluded = set(self.config.universe.excluded_symbols)
        ranked: list[RankedSymbol] = []
        for underlying in underlyings:
            symbol = underlying.symbol.upper()
            if symbol in excluded:
                continue
            if underlying.halted:
                ranked.append(RankedSymbol(symbol, 0.0, ["halted"]))
                continue
            if self.config.liquidity.avoid_earnings and underlying.earnings_today:
                ranked.append(RankedSymbol(symbol, 0.0, ["earnings risk"]))
                continue
            if self.config.liquidity.avoid_scheduled_news and underlying.scheduled_news_risk:
                ranked.append(RankedSymbol(symbol, 0.0, ["scheduled news risk"]))
                continue
            score, reasons = self._score_symbol(underlying, chains.get(symbol, []))
            ranked.append(RankedSymbol(symbol, round(score, 2), reasons))
        return sorted(ranked, key=lambda item: item.score, reverse=True)[
            : self.config.universe.max_symbols_per_scan
        ]

    def _score_symbol(
        self,
        underlying: UnderlyingSnapshot,
        contracts: list[OptionContract],
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        if not contracts:
            return 0.0, ["no option chain data"]

        liquid_scores = [liquidity_score(contract, self.config.liquidity) for contract in contracts]
        avg_liquidity = mean(liquid_scores) if liquid_scores else 0.0
        affordable = [
            contract
            for contract in contracts
            if contract.ask is not None and contract.ask <= self.config.universe.max_contract_price
        ]
        capital_efficiency = min(100.0, len(affordable) / max(1, len(contracts)) * 140.0)
        volatility = 50.0
        if underlying.realized_volatility is not None:
            volatility = max(0.0, min(100.0, underlying.realized_volatility * 100.0))
        elif underlying.atr is not None and underlying.price > 0:
            volatility = max(0.0, min(100.0, (underlying.atr / underlying.price) * 2500.0))

        movement = 50.0
        if underlying.intraday_change_pct is not None:
            movement = max(0.0, min(100.0, 50.0 + abs(underlying.intraday_change_pct) * 1200.0))

        score = (
            avg_liquidity * 0.38
            + volatility * 0.20
            + movement * 0.20
            + capital_efficiency * 0.22
        )
        reasons.extend(
            [
                f"liquidity={avg_liquidity:.1f}",
                f"volatility={volatility:.1f}",
                f"intraday_opportunity={movement:.1f}",
                f"affordable_contracts={len(affordable)}",
            ]
        )
        return score, reasons

