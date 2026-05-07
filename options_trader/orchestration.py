"""Strategy orchestration shared by CLI commands."""

from __future__ import annotations

from datetime import date

from options_trader.config.models import BotConfig
from options_trader.domain import (
    AccountState,
    OptionContract,
    Position,
    StrategyKind,
    TradeDecision,
    UnderlyingSnapshot,
)
from options_trader.risk import RiskManager, assess_account_capabilities
from options_trader.signals.technical import TechnicalSnapshot
from options_trader.strategies import LongOptionsStrategy, StrategyContext, VerticalSpreadStrategy, WheelStrategy


def generate_and_filter_candidates(
    config: BotConfig,
    account: AccountState,
    chains: dict[str, list[OptionContract]],
    underlyings: dict[str, UnderlyingSnapshot],
    technicals: dict[str, TechnicalSnapshot],
    positions: list[Position] | None = None,
    today: date | None = None,
) -> TradeDecision:
    positions = positions or []
    context = StrategyContext(
        config=config,
        account=account,
        today=today or date.today(),
        underlyings=underlyings,
        technicals=technicals,
        positions=positions,
    )
    decision = TradeDecision()
    all_candidates = []
    strategies = [
        (StrategyKind.LONG_OPTIONS, LongOptionsStrategy()),
        (StrategyKind.WHEEL, WheelStrategy()),
        (StrategyKind.VERTICAL_SPREADS, VerticalSpreadStrategy()),
    ]
    all_contracts = [contract for contracts in chains.values() for contract in contracts]
    for kind, strategy in strategies:
        capability = assess_account_capabilities(account, kind, config)
        if not capability.eligible:
            for reason, message in zip(capability.rejections, capability.messages, strict=False):
                decision.add_rejection(reason, f"{kind.value}: {message}")
            continue
        all_candidates.extend(strategy.generate(all_contracts, context))

    risk_decision = RiskManager(config).evaluate(all_candidates, account)
    decision.accepted.extend(risk_decision.accepted)
    decision.rejected.extend(risk_decision.rejected)
    decision.accepted.sort(key=lambda candidate: candidate.score, reverse=True)
    return decision

