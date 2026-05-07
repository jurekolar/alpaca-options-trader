"""Defined-risk debit vertical spread strategy."""

from __future__ import annotations

from collections import defaultdict

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


class VerticalSpreadStrategy(Strategy):
    name = StrategyKind.VERTICAL_SPREADS.value

    def generate(self, contracts: list[OptionContract], context: StrategyContext) -> list[TradeCandidate]:
        if not context.config.strategies.vertical_spreads_enabled:
            return []
        if not context.account.multi_leg_supported:
            return []
        scorer = TradeScorer(context.config)
        liquid = [
            contract
            for contract in contracts
            if not option_quality_rejections(
                contract,
                context.config.liquidity,
                context.config.universe,
                context.today,
            )
        ]
        by_group: dict[tuple[str, object, OptionRight], list[OptionContract]] = defaultdict(list)
        for contract in liquid:
            by_group[(contract.underlying_symbol, contract.expiration_date, contract.right)].append(contract)

        candidates: list[TradeCandidate] = []
        for (_, _, right), group in by_group.items():
            sorted_group = sorted(group, key=lambda c: c.strike_price)
            if right == OptionRight.CALL and self._is_bullish(sorted_group[0].underlying_symbol, context):
                candidates.extend(self._call_debit_spreads(sorted_group, context, scorer))
            if right == OptionRight.PUT and self._is_bearish(sorted_group[0].underlying_symbol, context):
                candidates.extend(self._put_debit_spreads(sorted_group, context, scorer))
        return sorted(candidates, key=lambda item: item.score, reverse=True)

    def _call_debit_spreads(
        self,
        group: list[OptionContract],
        context: StrategyContext,
        scorer: TradeScorer,
    ) -> list[TradeCandidate]:
        candidates: list[TradeCandidate] = []
        for long_leg in group:
            for short_leg in group:
                width = short_leg.strike_price - long_leg.strike_price
                if width <= 0 or width > context.config.strategies.vertical_max_width:
                    continue
                candidate = self._build_candidate(long_leg, short_leg, width, context)
                if candidate:
                    scorer.score(
                        candidate,
                        context.account,
                        context.underlyings.get(candidate.underlying_symbol),
                        context.technicals.get(candidate.underlying_symbol),
                    )
                    candidates.append(candidate)
        return candidates

    def _put_debit_spreads(
        self,
        group: list[OptionContract],
        context: StrategyContext,
        scorer: TradeScorer,
    ) -> list[TradeCandidate]:
        candidates: list[TradeCandidate] = []
        for long_leg in reversed(group):
            for short_leg in reversed(group):
                width = long_leg.strike_price - short_leg.strike_price
                if width <= 0 or width > context.config.strategies.vertical_max_width:
                    continue
                candidate = self._build_candidate(long_leg, short_leg, width, context)
                if candidate:
                    scorer.score(
                        candidate,
                        context.account,
                        context.underlyings.get(candidate.underlying_symbol),
                        context.technicals.get(candidate.underlying_symbol),
                    )
                    candidates.append(candidate)
        return candidates

    def _build_candidate(
        self,
        long_contract: OptionContract,
        short_contract: OptionContract,
        width: float,
        context: StrategyContext,
    ) -> TradeCandidate | None:
        if long_contract.ask is None or short_contract.bid is None:
            return None
        debit = max(0.0, long_contract.ask - short_contract.bid)
        if debit <= 0:
            return None
        max_loss = debit * 100
        max_profit = max(0.0, width * 100 - max_loss)
        if max_profit <= 0:
            return None
        if max_profit / max_loss < context.config.strategies.vertical_min_reward_risk:
            return None
        return TradeCandidate(
            strategy=StrategyKind.VERTICAL_SPREADS,
            underlying_symbol=long_contract.underlying_symbol,
            legs=[
                OptionLeg(contract=long_contract, action=TradeAction.BUY_TO_OPEN),
                OptionLeg(contract=short_contract, action=TradeAction.SELL_TO_OPEN),
            ],
            quantity=1,
            max_loss=max_loss,
            expected_reward=max_profit,
            buying_power_effect=max_loss,
            score=0.0,
            rationale=[
                "defined-risk debit vertical",
                f"spread_width={width:.2f}",
                f"debit={debit:.2f}",
                f"max_profit={max_profit:.2f}",
            ],
        )

    def _is_bullish(self, symbol: str, context: StrategyContext) -> bool:
        technical = context.technicals.get(symbol)
        underlying = context.underlyings.get(symbol)
        return bool(
            (technical and technical.momentum_score >= 55.0)
            or (underlying and underlying.intraday_change_pct is not None and underlying.intraday_change_pct > 0.003)
        )

    def _is_bearish(self, symbol: str, context: StrategyContext) -> bool:
        technical = context.technicals.get(symbol)
        underlying = context.underlyings.get(symbol)
        return bool(
            (technical and technical.momentum_score <= 45.0)
            or (underlying and underlying.intraday_change_pct is not None and underlying.intraday_change_pct < -0.003)
        )

