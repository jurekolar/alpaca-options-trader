"""Trade scoring that combines technical, options, liquidity, and risk/reward inputs."""

from __future__ import annotations

from dataclasses import dataclass

from options_trader.config.models import BotConfig
from options_trader.domain import AccountState, TradeCandidate, UnderlyingSnapshot
from options_trader.signals.options import capital_efficiency_score, liquidity_score, risk_reward_score
from options_trader.signals.technical import TechnicalSnapshot


@dataclass(frozen=True)
class ScoreBreakdown:
    liquidity: float
    momentum: float
    volatility: float
    capital_efficiency: float
    risk_reward: float
    total: float


class TradeScorer:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def score(
        self,
        candidate: TradeCandidate,
        account: AccountState,
        underlying: UnderlyingSnapshot | None = None,
        technical: TechnicalSnapshot | None = None,
    ) -> ScoreBreakdown:
        first_leg = candidate.legs[0].contract
        liq = liquidity_score(first_leg, self.config.liquidity)
        momentum = technical.momentum_score if technical else 50.0
        vol = self._volatility_component(underlying, technical)
        capital = capital_efficiency_score(
            candidate.max_loss,
            candidate.buying_power_effect,
            max(1.0, account.cash),
        )
        rr = risk_reward_score(candidate.max_loss, candidate.expected_reward)

        weights = self.config.scoring
        total = (
            liq * weights.liquidity_weight
            + momentum * weights.momentum_weight
            + vol * weights.volatility_weight
            + capital * weights.capital_efficiency_weight
            + rr * weights.risk_reward_weight
        )
        candidate.score = round(total, 2)
        candidate.rationale.extend(
            [
                f"liquidity={liq:.1f}",
                f"momentum={momentum:.1f}",
                f"volatility={vol:.1f}",
                f"capital_efficiency={capital:.1f}",
                f"risk_reward={rr:.1f}",
            ]
        )
        return ScoreBreakdown(liq, momentum, vol, capital, rr, round(total, 2))

    def _volatility_component(
        self,
        underlying: UnderlyingSnapshot | None,
        technical: TechnicalSnapshot | None,
    ) -> float:
        vol = None
        if underlying and underlying.realized_volatility is not None:
            vol = underlying.realized_volatility
        elif technical and technical.realized_volatility is not None:
            vol = technical.realized_volatility
        if vol is None:
            return 50.0
        return max(0.0, min(100.0, vol * 100.0))

