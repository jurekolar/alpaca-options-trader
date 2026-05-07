"""Alpaca options market-data normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
import re
from typing import Any, Iterable

from options_trader.domain import Greeks, OptionBar, OptionContract, OptionRight, Quote, UnderlyingSnapshot
from options_trader.exceptions import HistoricalDataUnavailableError, MarketDataUnavailableError
from options_trader.retry import retry_call
from options_trader.signals.technical import TechnicalSnapshot, compute_technical_snapshot

LOGGER = logging.getLogger(__name__)

OCC_SYMBOL_RE = re.compile(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$")


@dataclass(frozen=True)
class ParsedOptionSymbol:
    underlying: str
    expiration: date
    right: OptionRight
    strike: float


def parse_occ_option_symbol(symbol: str) -> ParsedOptionSymbol:
    match = OCC_SYMBOL_RE.match(symbol)
    if not match:
        raise ValueError(f"Unsupported OCC option symbol format: {symbol}")
    underlying, yymmdd, right, strike = match.groups()
    expiration = date(2000 + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6]))
    return ParsedOptionSymbol(
        underlying=underlying,
        expiration=expiration,
        right=OptionRight.CALL if right == "C" else OptionRight.PUT,
        strike=int(strike) / 1000.0,
    )


def _getattr_any(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class AlpacaMarketData:
    def __init__(
        self,
        option_data_client: Any,
        stock_data_client: Any | None = None,
        stock_feed: str | None = "iex",
    ) -> None:
        self.option_data_client = option_data_client
        self.stock_data_client = stock_data_client
        self.stock_feed = stock_feed.lower() if stock_feed else None

    def get_option_chain(
        self,
        underlying_symbol: str,
        expiration_date_gte: date | None = None,
        expiration_date_lte: date | None = None,
    ) -> list[OptionContract]:
        try:
            from alpaca.data.requests import OptionChainRequest
        except ImportError as exc:
            raise MarketDataUnavailableError("alpaca-py is not installed. Run: pip install alpaca-py") from exc

        request_kwargs: dict[str, Any] = {"underlying_symbol": underlying_symbol}
        if expiration_date_gte is not None:
            request_kwargs["expiration_date_gte"] = expiration_date_gte
        if expiration_date_lte is not None:
            request_kwargs["expiration_date_lte"] = expiration_date_lte
        request = OptionChainRequest(**request_kwargs)
        try:
            response = retry_call(
                lambda: self.option_data_client.get_option_chain(request),
                operation_name=f"option chain {underlying_symbol}",
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises API-specific exceptions across versions.
            raise MarketDataUnavailableError(f"Unable to fetch option chain for {underlying_symbol}: {exc}") from exc
        return [self._snapshot_to_contract(symbol, snapshot) for symbol, snapshot in _items(response)]

    def get_underlying_intraday_context(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[UnderlyingSnapshot, TechnicalSnapshot | None]:
        if self.stock_data_client is None:
            return UnderlyingSnapshot(symbol=symbol, price=0.0), None
        try:
            from alpaca.data.enums import DataFeed
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
        except ImportError as exc:
            raise MarketDataUnavailableError("alpaca-py is not installed. Run: pip install alpaca-py") from exc

        request_kwargs: dict[str, Any] = {
            "symbol_or_symbols": symbol,
            "timeframe": TimeFrame.Minute,
            "start": start,
            "end": end,
            "limit": 390,
        }
        if self.stock_feed is not None:
            try:
                request_kwargs["feed"] = DataFeed(self.stock_feed)
            except ValueError as exc:
                raise MarketDataUnavailableError(
                    f"Unsupported Alpaca stock data feed: {self.stock_feed}"
                ) from exc

        try:
            response = retry_call(
                lambda: self.stock_data_client.get_stock_bars(
                    StockBarsRequest(**request_kwargs)
                ),
                operation_name=f"stock bars {symbol}",
            )
        except Exception as exc:  # noqa: BLE001
            raise MarketDataUnavailableError(f"Unable to fetch stock bars for {symbol}: {exc}") from exc

        bars = list(_single_symbol_bars(response, symbol))
        if not bars:
            return UnderlyingSnapshot(symbol=symbol, price=0.0), None
        closes = [float(_getattr_any(bar, ["close", "c"], 0.0)) for bar in bars]
        highs = [float(_getattr_any(bar, ["high", "h"], 0.0)) for bar in bars]
        lows = [float(_getattr_any(bar, ["low", "l"], 0.0)) for bar in bars]
        volumes = [int(_getattr_any(bar, ["volume", "v"], 0) or 0) for bar in bars]
        technical = compute_technical_snapshot(closes, highs, lows, volumes)
        price = closes[-1] if closes else 0.0
        intraday_change = (price / closes[0] - 1.0) if len(closes) > 1 and closes[0] > 0 else None
        high_low_ranges = [high - low for high, low in zip(highs, lows)]
        atr = sum(high_low_ranges[-14:]) / min(14, len(high_low_ranges)) if high_low_ranges else None
        return (
            UnderlyingSnapshot(
                symbol=symbol,
                price=price,
                atr=atr,
                realized_volatility=technical.realized_volatility,
                intraday_change_pct=intraday_change,
                relative_volume=None,
                vwap_deviation_pct=technical.vwap_deviation_pct,
            ),
            technical,
        )

    def get_historical_bars(
        self,
        option_symbols: list[str],
        start: datetime,
        end: datetime,
        limit: int | None = None,
    ) -> dict[str, list[OptionBar]]:
        if not option_symbols:
            raise HistoricalDataUnavailableError("No option symbols supplied for historical data request")
        try:
            from alpaca.data.requests import OptionBarsRequest
            from alpaca.data.timeframe import TimeFrame
        except ImportError as exc:
            raise HistoricalDataUnavailableError("alpaca-py is not installed. Run: pip install alpaca-py") from exc

        request_kwargs = {
            "symbol_or_symbols": option_symbols,
            "timeframe": TimeFrame.Minute,
            "start": start,
            "end": end,
        }
        if limit is not None:
            request_kwargs["limit"] = limit
        request = OptionBarsRequest(**request_kwargs)
        try:
            response = retry_call(
                lambda: self.option_data_client.get_option_bars(request),
                operation_name=f"historical option bars {','.join(option_symbols)}",
            )
        except Exception as exc:  # noqa: BLE001
            raise HistoricalDataUnavailableError(
                f"Unable to fetch Alpaca historical option bars for {option_symbols}: {exc}"
            ) from exc
        bars = self._barset_to_domain(response)
        if not any(bars.values()):
            requested_symbols = ", ".join(option_symbols)
            raise HistoricalDataUnavailableError(
                "Alpaca returned no historical option bars for "
                f"{requested_symbols} between {start.isoformat()} and {end.isoformat()}; "
                "confirm the contract traded during that window or pass --start/--end explicitly. "
                "No synthetic fallback used."
            )
        return bars

    def _snapshot_to_contract(self, symbol: str, snapshot: Any) -> OptionContract:
        parsed = parse_occ_option_symbol(symbol)
        quote_obj = _getattr_any(snapshot, ["latest_quote", "quote"])
        quote = None
        if quote_obj is not None:
            bid = _float_or_none(_getattr_any(quote_obj, ["bid_price", "bp", "bid"]))
            ask = _float_or_none(_getattr_any(quote_obj, ["ask_price", "ap", "ask"]))
            if bid is not None and ask is not None:
                quote = Quote(
                    bid=bid,
                    ask=ask,
                    bid_size=_int_or_none(_getattr_any(quote_obj, ["bid_size", "bs"])) or 0,
                    ask_size=_int_or_none(_getattr_any(quote_obj, ["ask_size", "as"])) or 0,
                    timestamp=_getattr_any(quote_obj, ["timestamp", "t"]),
                )
        greeks_obj = _getattr_any(snapshot, ["greeks"])
        greeks = Greeks(
            delta=_float_or_none(_getattr_any(greeks_obj, ["delta"])),
            gamma=_float_or_none(_getattr_any(greeks_obj, ["gamma"])),
            theta=_float_or_none(_getattr_any(greeks_obj, ["theta"])),
            vega=_float_or_none(_getattr_any(greeks_obj, ["vega"])),
            rho=_float_or_none(_getattr_any(greeks_obj, ["rho"])),
        )
        return OptionContract(
            symbol=symbol,
            underlying_symbol=parsed.underlying,
            expiration_date=parsed.expiration,
            strike_price=parsed.strike,
            right=parsed.right,
            quote=quote,
            greeks=greeks,
            implied_volatility=_float_or_none(_getattr_any(snapshot, ["implied_volatility", "iv"])),
            open_interest=_int_or_none(_getattr_any(snapshot, ["open_interest"])),
            volume=_int_or_none(_getattr_any(snapshot, ["volume"])),
            tradable=bool(_getattr_any(snapshot, ["tradable"], True)),
        )

    def _barset_to_domain(self, response: Any) -> dict[str, list[OptionBar]]:
        data = _getattr_any(response, ["data"], response)
        result: dict[str, list[OptionBar]] = {}
        for symbol, bars in _items(data):
            parsed_bars = []
            for bar in bars:
                timestamp = _getattr_any(bar, ["timestamp", "t"])
                if timestamp is None:
                    continue
                parsed_bars.append(
                    OptionBar(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=float(_getattr_any(bar, ["open", "o"], 0.0)),
                        high=float(_getattr_any(bar, ["high", "h"], 0.0)),
                        low=float(_getattr_any(bar, ["low", "l"], 0.0)),
                        close=float(_getattr_any(bar, ["close", "c"], 0.0)),
                        volume=int(_getattr_any(bar, ["volume", "v"], 0) or 0),
                    )
                )
            result[symbol] = parsed_bars
        return result


def _items(response: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(response, dict):
        return response.items()
    if hasattr(response, "data") and isinstance(response.data, dict):
        return response.data.items()
    if hasattr(response, "items"):
        return response.items()
    raise MarketDataUnavailableError(f"Unsupported Alpaca response type: {type(response)!r}")


def _single_symbol_bars(response: Any, symbol: str) -> Iterable[Any]:
    data = _getattr_any(response, ["data"], response)
    if isinstance(data, dict):
        return data.get(symbol, []) or data.get(symbol.upper(), [])
    if hasattr(response, "data") and isinstance(response.data, dict):
        return response.data.get(symbol, []) or response.data.get(symbol.upper(), [])
    return []
