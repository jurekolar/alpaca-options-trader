"""Risk and account capability gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from os import environ
from typing import Mapping

from options_trader.config.models import BotConfig
from options_trader.domain import (
    AccountState,
    OptionRight,
    RejectionReason,
    StrategyKind,
    TradeAction,
    TradeCandidate,
    TradeDecision,
)
from options_trader.exceptions import CapabilityError, LiveTradingBlockedError
from options_trader.risk.sizing import PositionSizer


@dataclass(frozen=True)
class CapabilityAssessment:
    eligible: bool
    rejections: list[RejectionReason] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def require(self) -> None:
        if not self.eligible:
            raise CapabilityError("; ".join(self.messages))


def assert_live_trading_allowed(
    config: BotConfig,
    cli_ack: bool,
    env: Mapping[str, str] | None = None,
) -> None:
    env = env or environ
    missing: list[str] = []
    if not config.execution.live_trading_enabled:
        missing.append("config.execution.live_trading_enabled must be true")
    if not cli_ack:
        missing.append("CLI flag --i-understand-this-can-lose-money is required")
    if env.get("ALLOW_LIVE_TRADING") != "true":
        missing.append("environment variable ALLOW_LIVE_TRADING=true is required")
    if missing:
        raise LiveTradingBlockedError("Live trading blocked: " + "; ".join(missing))


def assess_account_capabilities(
    account: AccountState,
    strategy: StrategyKind,
    config: BotConfig,
) -> CapabilityAssessment:
    rejections: list[RejectionReason] = []
    messages: list[str] = []

    if not account.options_approved:
        rejections.append(RejectionReason.OPTIONS_NOT_APPROVED)
        messages.append("Alpaca account is not approved for options trading")

    required_level = config.strategies.min_options_level_long
    if strategy == StrategyKind.VERTICAL_SPREADS:
        required_level = config.strategies.min_options_level_spreads
        if not account.multi_leg_supported:
            rejections.append(RejectionReason.MISSING_MULTI_LEG_SUPPORT)
            messages.append("multi-leg option orders are not supported for this account")
    elif strategy == StrategyKind.WHEEL:
        required_level = config.strategies.min_options_level_short

    if account.options_trading_level < required_level:
        rejections.append(RejectionReason.OPTIONS_LEVEL_TOO_LOW)
        messages.append(
            f"options trading level {account.options_trading_level} is below required level "
            f"{required_level} for {strategy.value}"
        )

    if not account.market_data_entitled:
        rejections.append(RejectionReason.MARKET_DATA_UNAVAILABLE)
        messages.append("options market data entitlement could not be verified")

    return CapabilityAssessment(eligible=not rejections, rejections=rejections, messages=messages)


@dataclass
class RiskManager:
    config: BotConfig
    realized_pnl_today: float = 0.0
    peak_equity: float | None = None
    open_positions_count: int = 0
    trades_today: int = 0

    def evaluate(self, candidates: list[TradeCandidate], account: AccountState) -> TradeDecision:
        decision = TradeDecision()
        sizer = PositionSizer(self.config.risk)
        self.peak_equity = max(self.peak_equity or account.equity, account.equity)

        for candidate in candidates:
            rejection = self._first_rejection(candidate, account, sizer)
            if rejection is not None:
                reason, message = rejection
                decision.add_rejection(reason, message, candidate)
                continue

            qty = sizer.affordable_quantity(candidate, account)
            if qty <= 0:
                decision.add_rejection(
                    RejectionReason.OVERSIZED_POSITION,
                    "candidate exceeds per-trade risk, buying power, or max position notional",
                    candidate,
                )
                continue
            candidate.quantity = qty
            decision.accepted.append(candidate)
        return decision

    def _first_rejection(
        self,
        candidate: TradeCandidate,
        account: AccountState,
        sizer: PositionSizer,
    ) -> tuple[RejectionReason, str] | None:
        if self.realized_pnl_today <= -(account.equity * self.config.risk.max_daily_loss_pct):
            return RejectionReason.DAILY_LOSS_LIMIT, "max daily loss reached"

        peak = self.peak_equity or account.equity
        drawdown = (peak - account.equity) / peak if peak > 0 else 0.0
        if drawdown >= self.config.risk.max_drawdown_pct:
            return RejectionReason.DRAWDOWN_LIMIT, "max drawdown reached"

        if self.open_positions_count >= self.config.risk.max_open_positions:
            return RejectionReason.MAX_POSITIONS, "max open positions reached"

        if self.trades_today >= self.config.risk.max_trades_per_day:
            return RejectionReason.MAX_TRADES_PER_DAY, "max trades per day reached"

        if not candidate.is_defined_risk:
            return RejectionReason.NAKED_SHORT_NOT_ALLOWED, "undefined-risk options are disabled"

        if self._has_naked_short(candidate):
            return RejectionReason.NAKED_SHORT_NOT_ALLOWED, "naked short option leg detected"

        if candidate.score < self.config.scoring.min_trade_score:
            return RejectionReason.LOW_SCORE, f"score {candidate.score:.1f} below configured threshold"

        if candidate.buying_power_effect > account.effective_options_buying_power:
            return RejectionReason.INSUFFICIENT_BUYING_POWER, "candidate exceeds options buying power"

        if candidate.max_loss > sizer.max_trade_risk_dollars(account):
            return (
                RejectionReason.OVERSIZED_POSITION,
                "candidate max loss exceeds configured account risk per trade",
            )

        return None

    def _has_naked_short(self, candidate: TradeCandidate) -> bool:
        if self.config.risk.allow_naked_short_options:
            return False
        short_legs = [leg for leg in candidate.legs if leg.action == TradeAction.SELL_TO_OPEN]
        if not short_legs:
            return False
        if candidate.strategy == StrategyKind.WHEEL:
            return False
        if candidate.strategy == StrategyKind.VERTICAL_SPREADS:
            for short_leg in short_legs:
                covered = any(
                    long_leg.action == TradeAction.BUY_TO_OPEN
                    and long_leg.contract.right == short_leg.contract.right
                    and long_leg.contract.expiration_date == short_leg.contract.expiration_date
                    and (
                        (
                            short_leg.contract.right == OptionRight.CALL
                            and long_leg.contract.strike_price < short_leg.contract.strike_price
                        )
                        or (
                            short_leg.contract.right == OptionRight.PUT
                            and long_leg.contract.strike_price > short_leg.contract.strike_price
                        )
                    )
                    for long_leg in candidate.legs
                )
                if not covered:
                    return True
            return False
        return True

