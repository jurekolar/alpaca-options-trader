"""Wheel strategy components with strict assignment-risk gates."""

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


class WheelStrategy(Strategy):
    name = StrategyKind.WHEEL.value

    def generate(self, contracts: list[OptionContract], context: StrategyContext) -> list[TradeCandidate]:
        if not context.config.strategies.wheel_enabled:
            return []
        scorer = TradeScorer(context.config)
        candidates: list[TradeCandidate] = []
        candidates.extend(self._cash_secured_puts(contracts, context, scorer))
        candidates.extend(self._covered_calls(contracts, context, scorer))
        return sorted(candidates, key=lambda item: item.score, reverse=True)

    def _cash_secured_puts(
        self,
        contracts: list[OptionContract],
        context: StrategyContext,
        scorer: TradeScorer,
    ) -> list[TradeCandidate]:
        candidates: list[TradeCandidate] = []
        cash_with_buffer = context.account.cash / (1.0 + context.config.strategies.wheel_min_cash_buffer_pct)
        for contract in contracts:
            if contract.right != OptionRight.PUT:
                continue
            if option_quality_rejections(
                contract,
                context.config.liquidity,
                context.config.universe,
                context.today,
            ):
                continue
            if contract.bid is None or contract.bid <= 0:
                continue
            assignment_notional = contract.strike_price * 100
            if assignment_notional > cash_with_buffer:
                continue
            premium = contract.bid * 100
            max_loss = max(0.0, assignment_notional - premium)
            candidate = TradeCandidate(
                strategy=StrategyKind.WHEEL,
                underlying_symbol=contract.underlying_symbol,
                legs=[OptionLeg(contract=contract, action=TradeAction.SELL_TO_OPEN)],
                quantity=1,
                max_loss=max_loss,
                expected_reward=premium,
                buying_power_effect=assignment_notional,
                score=0.0,
                rationale=[
                    "cash-secured put",
                    "assignment risk covered by cash",
                    f"assignment_notional={assignment_notional:.2f}",
                ],
            )
            scorer.score(
                candidate,
                context.account,
                context.underlyings.get(contract.underlying_symbol),
                context.technicals.get(contract.underlying_symbol),
            )
            candidates.append(candidate)
        return candidates

    def _covered_calls(
        self,
        contracts: list[OptionContract],
        context: StrategyContext,
        scorer: TradeScorer,
    ) -> list[TradeCandidate]:
        share_positions = {
            position.symbol.upper(): position
            for position in context.positions
            if position.asset_class == "us_equity" and position.qty >= 100
        }
        if not share_positions:
            return []

        candidates: list[TradeCandidate] = []
        for contract in contracts:
            if contract.right != OptionRight.CALL:
                continue
            if contract.underlying_symbol.upper() not in share_positions:
                continue
            if option_quality_rejections(
                contract,
                context.config.liquidity,
                context.config.universe,
                context.today,
            ):
                continue
            if contract.bid is None or contract.bid <= 0:
                continue
            premium = contract.bid * 100
            candidate = TradeCandidate(
                strategy=StrategyKind.WHEEL,
                underlying_symbol=contract.underlying_symbol,
                legs=[OptionLeg(contract=contract, action=TradeAction.SELL_TO_OPEN)],
                quantity=1,
                max_loss=0.0,
                expected_reward=premium,
                buying_power_effect=0.0,
                score=0.0,
                rationale=["covered call", "covered by at least 100 shares"],
                metadata={"covered_by": share_positions[contract.underlying_symbol.upper()].symbol},
            )
            scorer.score(
                candidate,
                context.account,
                context.underlyings.get(contract.underlying_symbol),
                context.technicals.get(contract.underlying_symbol),
            )
            candidates.append(candidate)
        return candidates
