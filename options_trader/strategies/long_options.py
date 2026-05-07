"""Long calls and puts for low-capital accounts.

This is the default deployable strategy for a $100 account because max loss is the
premium paid. Entries are intended for intraday momentum or volatility breakout
setups and always use buy-to-open option legs.
"""

from __future__ import annotations

from options_trader.domain import (
    OptionContract,
    OptionLeg,
    OptionRight,
    StrategyKind,
    TradeAction,
    TradeCandidate,
)
from options_trader.signals.options import option_quality_rejections
from options_trader.signals.scoring import TradeScorer
from options_trader.strategies.base import Strategy, StrategyContext


class LongOptionsStrategy(Strategy):
    name = StrategyKind.LONG_OPTIONS.value

    def generate(self, contracts: list[OptionContract], context: StrategyContext) -> list[TradeCandidate]:
        if not context.config.strategies.long_options_enabled:
            return []
        scorer = TradeScorer(context.config)
        candidates: list[TradeCandidate] = []
        for contract in contracts:
            if option_quality_rejections(
                contract,
                context.config.liquidity,
                context.config.universe,
                context.today,
            ):
                continue
            ask = contract.ask
            if ask is None or ask <= 0:
                continue
            direction_ok = self._direction_matches(contract, context)
            if not direction_ok:
                continue
            premium_cost = ask * 100
            expected_reward = premium_cost * context.config.strategies.long_take_profit_pct
            candidate = TradeCandidate(
                strategy=StrategyKind.LONG_OPTIONS,
                underlying_symbol=contract.underlying_symbol,
                legs=[OptionLeg(contract=contract, action=TradeAction.BUY_TO_OPEN)],
                quantity=1,
                max_loss=premium_cost,
                expected_reward=expected_reward,
                buying_power_effect=premium_cost,
                score=0.0,
                rationale=[
                    "defined-risk long option",
                    f"stop_loss={context.config.strategies.long_stop_loss_pct:.0%}",
                    f"take_profit={context.config.strategies.long_take_profit_pct:.0%}",
                ],
            )
            scorer.score(
                candidate,
                context.account,
                context.underlyings.get(contract.underlying_symbol),
                context.technicals.get(contract.underlying_symbol),
            )
            candidates.append(candidate)
        return sorted(candidates, key=lambda item: item.score, reverse=True)

    def _direction_matches(self, contract: OptionContract, context: StrategyContext) -> bool:
        technical = context.technicals.get(contract.underlying_symbol)
        underlying = context.underlyings.get(contract.underlying_symbol)
        momentum = technical.momentum_score if technical else 50.0
        breakout = technical.breakout_score if technical else 50.0
        intraday_change = underlying.intraday_change_pct if underlying else None
        bullish = momentum >= 58.0 or breakout >= 75.0 or (intraday_change is not None and intraday_change > 0.005)
        bearish = momentum <= 42.0 or breakout <= 25.0 or (intraday_change is not None and intraday_change < -0.005)
        if contract.right == OptionRight.CALL:
            return bullish
        return bearish

