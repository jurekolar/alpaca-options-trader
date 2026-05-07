"""Option-specific quality and risk-adjusted scoring helpers."""

from __future__ import annotations

from datetime import date

from options_trader.config.models import LiquidityConfig, UniverseConfig
from options_trader.domain import OptionContract, RejectionReason


def option_quality_rejections(
    contract: OptionContract,
    liquidity: LiquidityConfig,
    universe: UniverseConfig,
    today: date | None = None,
) -> list[RejectionReason]:
    rejections: list[RejectionReason] = []
    dte = contract.dte(today)
    if dte == 0 and not universe.allow_zero_dte:
        rejections.append(RejectionReason.ZERO_DTE_DISABLED)
    if dte < universe.min_dte or dte > universe.max_dte:
        rejections.append(RejectionReason.INVALID_STRATEGY)
    if not contract.tradable:
        rejections.append(RejectionReason.ILLIQUID_CONTRACT)
    if contract.open_interest is not None and contract.open_interest < liquidity.min_open_interest:
        rejections.append(RejectionReason.ILLIQUID_CONTRACT)
    if contract.volume is not None and contract.volume < liquidity.min_option_volume:
        rejections.append(RejectionReason.ILLIQUID_CONTRACT)
    if contract.quote is None:
        rejections.append(RejectionReason.MARKET_DATA_UNAVAILABLE)
    elif contract.quote.bid < liquidity.min_bid:
        rejections.append(RejectionReason.ILLIQUID_CONTRACT)
    elif contract.quote.spread_pct_of_mid > liquidity.max_bid_ask_spread_pct:
        rejections.append(RejectionReason.EXCESSIVE_SPREAD)
    if contract.ask is not None and contract.ask > universe.max_contract_price:
        rejections.append(RejectionReason.OVERSIZED_POSITION)
    return rejections


def liquidity_score(contract: OptionContract, liquidity: LiquidityConfig) -> float:
    if contract.quote is None:
        return 0.0
    spread_component = max(
        0.0,
        100.0 * (1.0 - contract.quote.spread_pct_of_mid / liquidity.max_bid_ask_spread_pct),
    )
    oi = contract.open_interest if contract.open_interest is not None else 0
    vol = contract.volume if contract.volume is not None else 0
    oi_component = min(100.0, oi / max(1, liquidity.min_open_interest) * 50.0)
    vol_component = min(100.0, vol / max(1, liquidity.min_option_volume) * 50.0)
    return max(0.0, min(100.0, 0.50 * spread_component + 0.25 * oi_component + 0.25 * vol_component))


def capital_efficiency_score(max_loss: float, buying_power_effect: float, account_cash: float) -> float:
    if max_loss <= 0 or buying_power_effect <= 0 or account_cash <= 0:
        return 0.0
    risk_fraction = max_loss / account_cash
    bp_fraction = buying_power_effect / account_cash
    risk_score = max(0.0, 100.0 * (1.0 - risk_fraction))
    bp_score = max(0.0, 100.0 * (1.0 - bp_fraction))
    return min(100.0, 0.65 * risk_score + 0.35 * bp_score)


def risk_reward_score(max_loss: float, expected_reward: float) -> float:
    if max_loss <= 0 or expected_reward <= 0:
        return 0.0
    ratio = expected_reward / max_loss
    return max(0.0, min(100.0, ratio * 50.0))

