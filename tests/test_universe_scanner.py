from __future__ import annotations

from datetime import date, timedelta
import unittest

from options_trader.config.models import BotConfig
from options_trader.domain import OptionContract, OptionRight, Quote, UnderlyingSnapshot
from options_trader.universe import UniverseScanner


def option(symbol: str, bid: float, ask: float) -> OptionContract:
    return OptionContract(
        symbol=symbol,
        underlying_symbol="NVDA",
        expiration_date=date.today() + timedelta(days=5),
        strike_price=200.0,
        right=OptionRight.CALL,
        quote=Quote(bid=bid, ask=ask),
        open_interest=500,
        volume=50,
    )


class UniverseScannerTests(unittest.TestCase):
    def test_rank_requires_strategy_eligible_contracts(self) -> None:
        config = BotConfig()
        scanner = UniverseScanner(config)

        ranked = scanner.rank(
            [UnderlyingSnapshot("NVDA", price=200.0)],
            {"NVDA": [option("NVDA260515C00200000", bid=0.40, ask=0.50)]},
        )

        self.assertEqual(ranked[0].score, 0.0)
        self.assertIn("no strategy-eligible contracts", ranked[0].reasons[0])

    def test_rank_scores_cheap_liquid_contracts(self) -> None:
        config = BotConfig()
        scanner = UniverseScanner(config)

        ranked = scanner.rank(
            [
                UnderlyingSnapshot(
                    "NVDA",
                    price=200.0,
                    realized_volatility=0.40,
                    intraday_change_pct=0.01,
                )
            ],
            {"NVDA": [option("NVDA260515C00200000", bid=0.05, ask=0.06)]},
        )

        self.assertGreater(ranked[0].score, 0.0)
        self.assertIn("eligible_contracts=1", ranked[0].reasons)


if __name__ == "__main__":
    unittest.main()
