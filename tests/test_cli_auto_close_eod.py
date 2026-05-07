from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import cli
from options_trader.config.models import BotConfig, ExecutionConfig
from options_trader.domain import Position
from options_trader.exceptions import LiveTradingBlockedError, OptionsTraderError

EASTERN = ZoneInfo("America/New_York")


class FakeTradingClient:
    def __init__(self, *, timestamp: datetime, close: datetime, is_open: bool = True) -> None:
        self.clock = SimpleNamespace(timestamp=timestamp, is_open=is_open, next_close=close)
        self.calendar = [SimpleNamespace(close=close)]

    def get_clock(self) -> SimpleNamespace:
        return self.clock

    def get_calendar(self, _filters: object) -> list[SimpleNamespace]:
        return self.calendar


class FakeFactory:
    def __init__(self, trading_client: FakeTradingClient, positions: list[Position]) -> None:
        self._trading_client = trading_client
        self._positions = positions

    def trading_client(self) -> FakeTradingClient:
        return self._trading_client

    def positions(self) -> list[Position]:
        return self._positions


class FakeExecution:
    def __init__(self) -> None:
        self.closed_symbols: list[str] = []

    def close_position(self, symbol: str, qty: str | None = None) -> SimpleNamespace:
        self.closed_symbols.append(symbol)
        return SimpleNamespace(id=f"close-{symbol}", qty=qty)


def auto_close_args(
    *,
    dry_run: bool = True,
    live: bool = False,
    force: bool = False,
    ack: bool = False,
) -> Namespace:
    return Namespace(
        dry_run=dry_run,
        live=live,
        force=force,
        i_understand_this_can_lose_money=ack,
    )


def option_position(symbol: str, qty: float = 1.0) -> Position:
    return Position(
        symbol=symbol,
        qty=qty,
        market_value=12.34,
        average_entry_price=0.10,
        asset_class="us_option",
    )


class CliAutoCloseEodTests(unittest.TestCase):
    def test_dry_run_selects_options_and_skips_stock_without_submit(self) -> None:
        execution = FakeExecution()
        output = self._run_auto_close(
            positions=[
                option_position("SPY260508C00500000"),
                Position(
                    "AAPL",
                    qty=3,
                    market_value=600,
                    average_entry_price=200,
                    asset_class="us_equity",
                ),
                option_position("QQQ260508P00400000", qty=0),
            ],
            execution=execution,
            args=auto_close_args(dry_run=True),
        )

        self.assertIn("SPY260508C00500000", output)
        self.assertIn("Skipped non-option positions: 1", output)
        self.assertIn("Dry run: no close requests submitted.", output)
        self.assertEqual(execution.closed_symbols, [])

    def test_auto_close_submits_one_close_per_open_option_position(self) -> None:
        execution = FakeExecution()
        output = self._run_auto_close(
            positions=[
                option_position("SPY260508C00500000"),
                Position(
                    "AAPL",
                    qty=3,
                    market_value=600,
                    average_entry_price=200,
                    asset_class="us_equity",
                ),
                option_position("QQQ260508P00400000", qty=0),
            ],
            execution=execution,
            args=auto_close_args(dry_run=False),
        )

        self.assertEqual(execution.closed_symbols, ["SPY260508C00500000"])
        self.assertIn("Close request submitted for SPY260508C00500000", output)

    def test_outside_window_is_refused_unless_force_is_passed(self) -> None:
        with self.assertRaises(OptionsTraderError):
            self._run_auto_close(
                positions=[],
                args=auto_close_args(dry_run=True),
                timestamp=datetime(2026, 5, 7, 19, 30, tzinfo=timezone.utc),
            )

        output = self._run_auto_close(
            positions=[],
            args=auto_close_args(dry_run=True, force=True),
            timestamp=datetime(2026, 5, 7, 19, 30, tzinfo=timezone.utc),
        )

        self.assertIn("Force enabled", output)
        self.assertIn("No open option positions to close.", output)

    def test_live_mode_requires_existing_live_safety_gates(self) -> None:
        with self.assertRaises(LiveTradingBlockedError):
            cli.cmd_auto_close_eod(auto_close_args(live=True, ack=False), BotConfig())

    def test_paper_trade_blocks_new_entry_submit_inside_eod_window(self) -> None:
        factory = FakeFactory(
            FakeTradingClient(
                timestamp=datetime(2026, 5, 7, 19, 55, tzinfo=timezone.utc),
                close=datetime(2026, 5, 7, 16, 0, tzinfo=EASTERN),
            ),
            positions=[],
        )
        decision = SimpleNamespace(accepted=[object()])
        stdout = StringIO()
        with (
            patch.object(cli, "run_scan", return_value=([], decision, factory)),
            patch.object(cli, "format_scan_report", return_value="scan report"),
            patch.object(cli, "AlpacaExecutionClient") as execution_cls,
            redirect_stdout(stdout),
        ):
            result = cli.cmd_paper_trade(Namespace(dry_run=False), BotConfig())

        self.assertEqual(result, 0)
        self.assertIn("New entries blocked near close", stdout.getvalue())
        execution_cls.assert_not_called()

    def _run_auto_close(
        self,
        *,
        positions: list[Position],
        args: Namespace,
        execution: FakeExecution | None = None,
        timestamp: datetime = datetime(2026, 5, 7, 19, 55, tzinfo=timezone.utc),
    ) -> str:
        trading_client = FakeTradingClient(
            timestamp=timestamp,
            close=datetime(2026, 5, 7, 16, 0, tzinfo=EASTERN),
        )
        factory = FakeFactory(trading_client, positions)
        execution = execution or FakeExecution()
        config = BotConfig(execution=ExecutionConfig(liquidation_minutes_before_close=10))
        stdout = StringIO()
        with (
            patch.object(cli.AlpacaSettings, "from_env", return_value=object()),
            patch.object(cli, "AlpacaClientFactory", return_value=factory),
            patch.object(cli, "AlpacaExecutionClient", return_value=execution),
            redirect_stdout(stdout),
        ):
            cli.cmd_auto_close_eod(args, config)
        return stdout.getvalue()


if __name__ == "__main__":
    unittest.main()
