from __future__ import annotations

from datetime import date, timedelta
import unittest

from options_trader.config.models import BotConfig
from options_trader.domain import (
    AccountState,
    OptionContract,
    OptionLeg,
    OptionRight,
    Quote,
    StrategyKind,
    TradeAction,
    TradeCandidate,
    UnderlyingSnapshot,
)
from options_trader.risk import RiskManager, assess_account_capabilities
from options_trader.signals.technical import TechnicalSnapshot
from options_trader.strategies import LongOptionsStrategy, StrategyContext, VerticalSpreadStrategy, WheelStrategy


def option(
    symbol: str,
    underlying: str = "SPY",
    strike: float = 100.0,
    right: OptionRight = OptionRight.CALL,
    bid: float = 0.10,
    ask: float = 0.12,
) -> OptionContract:
    return OptionContract(
        symbol=symbol,
        underlying_symbol=underlying,
        expiration_date=date.today() + timedelta(days=3),
        strike_price=strike,
        right=right,
        quote=Quote(bid=bid, ask=ask),
        open_interest=500,
        volume=50,
    )


def account(level: int = 3, cash: float = 100.0) -> AccountState:
    return AccountState(
        equity=cash,
        cash=cash,
        buying_power=cash,
        options_buying_power=cash,
        paper=True,
        options_approved=level > 0,
        options_trading_level=level,
        multi_leg_supported=level >= 3,
        market_data_entitled=True,
    )


def bullish_technical() -> TechnicalSnapshot:
    return TechnicalSnapshot(
        rsi=62,
        short_ma=101,
        long_ma=100,
        trend_score=75,
        momentum_score=70,
        volume_spike_score=60,
        breakout_score=80,
        realized_volatility=0.45,
        vwap_deviation_pct=0.01,
    )


class RiskAndStrategyTests(unittest.TestCase):
    def test_long_call_generates_for_bullish_setup(self) -> None:
        config = BotConfig()
        ctx = StrategyContext(
            config=config,
            account=account(),
            today=date.today(),
            underlyings={"SPY": UnderlyingSnapshot("SPY", price=100.0, intraday_change_pct=0.01)},
            technicals={"SPY": bullish_technical()},
        )
        candidates = LongOptionsStrategy().generate([option("SPY260508C00100000")], ctx)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].strategy, StrategyKind.LONG_OPTIONS)
        self.assertGreater(candidates[0].score, 0)

    def test_wheel_rejects_when_assignment_notional_exceeds_100_cash(self) -> None:
        config = BotConfig()
        ctx = StrategyContext(config=config, account=account(cash=100), today=date.today())
        put = option("SPY260508P00100000", right=OptionRight.PUT, strike=100.0, bid=0.20, ask=0.25)
        self.assertEqual(WheelStrategy().generate([put], ctx), [])

    def test_vertical_requires_multileg_support(self) -> None:
        config = BotConfig()
        ctx = StrategyContext(
            config=config,
            account=account(level=2),
            today=date.today(),
            underlyings={"SPY": UnderlyingSnapshot("SPY", price=100.0, intraday_change_pct=0.01)},
            technicals={"SPY": bullish_technical()},
        )
        c1 = option("SPY260508C00100000", strike=100.0, ask=0.20)
        c2 = option("SPY260508C00101000", strike=101.0, bid=0.10, ask=0.11)
        self.assertEqual(VerticalSpreadStrategy().generate([c1, c2], ctx), [])

    def test_capability_assessment_flags_level_for_spreads(self) -> None:
        assessment = assess_account_capabilities(account(level=2), StrategyKind.VERTICAL_SPREADS, BotConfig())
        self.assertFalse(assessment.eligible)

    def test_risk_manager_rejects_oversized_long_option(self) -> None:
        config = BotConfig()
        contract = option("SPY260508C00100000", ask=0.20)
        candidate = TradeCandidate(
            strategy=StrategyKind.LONG_OPTIONS,
            underlying_symbol="SPY",
            legs=[OptionLeg(contract=contract, action=TradeAction.BUY_TO_OPEN)],
            quantity=1,
            max_loss=20.0,
            expected_reward=16.0,
            buying_power_effect=20.0,
            score=90.0,
        )
        decision = RiskManager(config).evaluate([candidate], account(cash=100))
        self.assertEqual(len(decision.accepted), 0)
        self.assertEqual(len(decision.rejected), 1)


if __name__ == "__main__":
    unittest.main()

