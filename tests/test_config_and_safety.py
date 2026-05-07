from __future__ import annotations

import unittest

from options_trader.config import load_config
from options_trader.config.models import BotConfig, ExecutionConfig
from options_trader.exceptions import LiveTradingBlockedError
from options_trader.risk import assert_live_trading_allowed


class ConfigAndSafetyTests(unittest.TestCase):
    def test_default_config_is_paper_and_no_naked_shorts(self) -> None:
        config = load_config("config/default.toml")
        self.assertTrue(config.execution.paper_trading_default)
        self.assertFalse(config.execution.live_trading_enabled)
        self.assertFalse(config.risk.allow_naked_short_options)
        self.assertFalse(config.universe.allow_zero_dte)
        self.assertEqual(config.market_data.stock_feed, "iex")

    def test_live_gate_requires_all_three_controls(self) -> None:
        config = BotConfig()
        with self.assertRaises(LiveTradingBlockedError):
            assert_live_trading_allowed(config, cli_ack=False, env={})

    def test_live_gate_allows_when_config_cli_and_env_agree(self) -> None:
        config = BotConfig(execution=ExecutionConfig(live_trading_enabled=True))
        assert_live_trading_allowed(
            config,
            cli_ack=True,
            env={"ALLOW_LIVE_TRADING": "true"},
        )


if __name__ == "__main__":
    unittest.main()
