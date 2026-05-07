"""Client construction and account verification for Alpaca."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from options_trader.config.env import environment_with_dotenv
from options_trader.domain import AccountState, Position
from options_trader.exceptions import MarketDataUnavailableError, MissingCredentialsError
from options_trader.retry import retry_call

LOGGER = logging.getLogger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _first_env(env: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AlpacaSettings:
    api_key: str
    secret_key: str
    paper: bool = True
    sandbox: bool = False

    @classmethod
    def from_env(
        cls,
        paper: bool = True,
        env: Mapping[str, str] | None = None,
        dotenv_path: str | Path | None = ".env",
    ) -> "AlpacaSettings":
        environ = environment_with_dotenv(env, dotenv_path)
        mode = "paper" if paper else "live"
        prefix = "ALPACA_PAPER" if paper else "ALPACA_LIVE"
        api_key = _first_env(
            environ,
            f"{prefix}_API_KEY_ID",
            f"{prefix}_KEY_ID",
            f"APCA_{mode.upper()}_API_KEY_ID",
            "ALPACA_API_KEY_ID",
            "APCA_API_KEY_ID",
        )
        secret_key = _first_env(
            environ,
            f"{prefix}_SECRET_KEY",
            f"{prefix}_API_SECRET_KEY",
            f"APCA_{mode.upper()}_SECRET_KEY",
            f"APCA_{mode.upper()}_API_SECRET_KEY",
            "ALPACA_SECRET_KEY",
            "APCA_API_SECRET_KEY",
        )
        if not api_key or not secret_key:
            raise MissingCredentialsError(
                f"Missing Alpaca {mode} credentials. Set {prefix}_API_KEY_ID and "
                f"{prefix}_SECRET_KEY in .env or the shell. Generic "
                "ALPACA_API_KEY_ID/ALPACA_SECRET_KEY and APCA_* variables are also accepted."
            )
        sandbox = _truthy(
            _first_env(
                environ,
                f"{prefix}_SANDBOX",
                f"APCA_{mode.upper()}_SANDBOX",
                "ALPACA_SANDBOX",
            )
        )
        return cls(api_key=api_key, secret_key=secret_key, paper=paper, sandbox=sandbox)


class AlpacaClientFactory:
    def __init__(self, settings: AlpacaSettings) -> None:
        self.settings = settings

    def trading_client(self) -> Any:
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise MissingCredentialsError("alpaca-py is not installed. Run: pip install alpaca-py") from exc
        return TradingClient(self.settings.api_key, self.settings.secret_key, paper=self.settings.paper)

    def option_data_client(self) -> Any:
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
        except ImportError as exc:
            raise MissingCredentialsError("alpaca-py is not installed. Run: pip install alpaca-py") from exc
        return OptionHistoricalDataClient(
            api_key=self.settings.api_key,
            secret_key=self.settings.secret_key,
            sandbox=self.settings.sandbox,
        )

    def stock_data_client(self) -> Any:
        try:
            from alpaca.data.historical.stock import StockHistoricalDataClient
        except ImportError as exc:
            raise MissingCredentialsError("alpaca-py is not installed. Run: pip install alpaca-py") from exc
        return StockHistoricalDataClient(api_key=self.settings.api_key, secret_key=self.settings.secret_key)

    def option_data_stream(self) -> Any:
        try:
            from alpaca.data.live.option import OptionDataStream
        except ImportError as exc:
            raise MissingCredentialsError("alpaca-py is not installed. Run: pip install alpaca-py") from exc
        return OptionDataStream(self.settings.api_key, self.settings.secret_key)

    def account_state(self, verify_market_data: bool = True) -> AccountState:
        trading = self.trading_client()
        account = trading.get_account()
        options_level = _to_int(getattr(account, "options_trading_level", 0), 0)
        approved_level = _to_int(getattr(account, "options_approved_level", 0), 0)
        options_buying_power = getattr(account, "options_buying_power", None)
        market_data_entitled = False
        if verify_market_data:
            market_data_entitled = self.verify_option_market_data()

        return AccountState(
            equity=_to_float(getattr(account, "equity", None)),
            cash=_to_float(getattr(account, "cash", None)),
            buying_power=_to_float(getattr(account, "buying_power", None)),
            options_buying_power=(
                None if options_buying_power is None else _to_float(options_buying_power, 0.0)
            ),
            paper=self.settings.paper,
            options_approved=approved_level > 0 or options_level > 0,
            options_trading_level=options_level,
            multi_leg_supported=options_level >= 3,
            market_data_entitled=market_data_entitled,
            day_trade_count=_to_int(getattr(account, "daytrade_count", 0), 0),
        )

    def positions(self) -> list[Position]:
        trading = self.trading_client()
        raw_positions = trading.get_all_positions()
        positions: list[Position] = []
        for raw in raw_positions:
            positions.append(
                Position(
                    symbol=str(getattr(raw, "symbol", "")),
                    qty=_to_float(getattr(raw, "qty", 0)),
                    market_value=_to_float(getattr(raw, "market_value", 0)),
                    average_entry_price=_to_float(getattr(raw, "avg_entry_price", 0)),
                    asset_class=str(getattr(raw, "asset_class", "")),
                    side=str(getattr(raw, "side", "")) or None,
                )
            )
        return positions

    def verify_option_market_data(self, probe_symbol: str = "SPY") -> bool:
        try:
            from alpaca.data.requests import OptionChainRequest
        except ImportError as exc:
            raise MissingCredentialsError("alpaca-py is not installed. Run: pip install alpaca-py") from exc

        client = self.option_data_client()
        try:
            response = retry_call(
                lambda: client.get_option_chain(OptionChainRequest(underlying_symbol=probe_symbol)),
                operation_name=f"option chain entitlement probe for {probe_symbol}",
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises API-specific exceptions across versions.
            raise MarketDataUnavailableError(
                f"Unable to verify options market data entitlement using {probe_symbol}: {exc}"
            ) from exc
        entitled = bool(response)
        if not entitled:
            LOGGER.warning("Option chain probe returned no data for %s", probe_symbol)
        return entitled
