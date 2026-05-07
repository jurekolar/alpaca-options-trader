"""Strategy interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from options_trader.config.models import BotConfig
from options_trader.domain import AccountState, OptionContract, Position, TradeCandidate, UnderlyingSnapshot
from options_trader.signals.technical import TechnicalSnapshot


@dataclass(frozen=True)
class StrategyContext:
    config: BotConfig
    account: AccountState
    today: date
    underlyings: dict[str, UnderlyingSnapshot] = field(default_factory=dict)
    technicals: dict[str, TechnicalSnapshot] = field(default_factory=dict)
    positions: list[Position] = field(default_factory=list)


class Strategy:
    name: str

    def generate(self, contracts: list[OptionContract], context: StrategyContext) -> list[TradeCandidate]:
        raise NotImplementedError

