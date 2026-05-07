from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from options_trader.backtesting.engine import BacktestResult, SimulatedTrade
from options_trader.domain import (
    OptionContract,
    OptionLeg,
    OptionRight,
    Quote,
    StrategyKind,
    TradeAction,
    TradeCandidate,
    TradeDecision,
)
from options_trader.reporting import format_universe_research_report
from options_trader.research import (
    CandidateBacktest,
    backtestable_candidate_symbols,
    research_symbol_universe,
)
from options_trader.universe.scanner import RankedSymbol


def contract(
    symbol: str,
    underlying: str = "NVDA",
    strike: float = 200.0,
    right: OptionRight = OptionRight.CALL,
) -> OptionContract:
    return OptionContract(
        symbol=symbol,
        underlying_symbol=underlying,
        expiration_date=date(2026, 5, 15),
        strike_price=strike,
        right=right,
        quote=Quote(bid=0.04, ask=0.05),
    )


class ResearchUniverseTests(unittest.TestCase):
    def test_research_symbol_universe_preserves_configured_priority_and_dedupes(self) -> None:
        symbols = research_symbol_universe(["SPY", "NVDA"], ["nvda", "XYZ"])

        self.assertEqual(symbols[:2], ["SPY", "NVDA"])
        self.assertEqual(symbols.count("NVDA"), 1)
        self.assertIn("XYZ", symbols)

    def test_backtestable_candidate_symbols_orders_vertical_long_then_short(self) -> None:
        long_contract = contract("NVDA260515C00200000", strike=200.0)
        short_contract = contract("NVDA260515C00202500", strike=202.5)
        candidate = TradeCandidate(
            strategy=StrategyKind.VERTICAL_SPREADS,
            underlying_symbol="NVDA",
            legs=[
                OptionLeg(short_contract, TradeAction.SELL_TO_OPEN),
                OptionLeg(long_contract, TradeAction.BUY_TO_OPEN),
            ],
            quantity=1,
            max_loss=10.0,
            expected_reward=15.0,
            buying_power_effect=10.0,
            score=80.0,
        )

        self.assertEqual(
            backtestable_candidate_symbols(candidate),
            ["NVDA260515C00200000", "NVDA260515C00202500"],
        )

    def test_research_report_recommends_profitable_occ_underlying(self) -> None:
        timestamp = datetime(2026, 5, 7, 14, 30, tzinfo=timezone.utc)
        result = BacktestResult(starting_cash=100.0, ending_cash=102.0)
        result.trades.append(
            SimulatedTrade(
                symbol="NVDA260515C00200000",
                strategy=StrategyKind.LONG_OPTIONS,
                entry_time=timestamp,
                exit_time=timestamp,
                entry_price=0.05,
                exit_price=0.07,
                quantity=1,
                pnl=2.0,
                max_loss=5.0,
                reason="take_profit",
            )
        )

        report = format_universe_research_report(
            ["NVDA"],
            [RankedSymbol("NVDA", 88.0, ["liquid"])],
            TradeDecision(),
            [CandidateBacktest(StrategyKind.LONG_OPTIONS, ["NVDA260515C00200000"], result=result)],
        )

        self.assertIn("## Recommended Symbols\n- NVDA", report)
        self.assertNotIn("NVDAC", report)


if __name__ == "__main__":
    unittest.main()
