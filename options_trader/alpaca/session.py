"""Market session timing helpers for Alpaca trading safeguards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from options_trader.config.models import ExecutionConfig
from options_trader.exceptions import OptionsTraderError
from options_trader.retry import retry_call

EXCHANGE_TIMEZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class MarketSessionTiming:
    current_time: datetime
    market_close_time: datetime | None
    is_open: bool
    minutes_until_close: float | None
    close_positions_before_eod: bool
    liquidation_minutes_before_close: int
    in_liquidation_window: bool

    @property
    def entry_orders_allowed(self) -> bool:
        return not self.in_liquidation_window


def get_market_session_timing(
    trading_client: Any,
    execution: ExecutionConfig,
) -> MarketSessionTiming:
    """Read Alpaca clock/calendar data and compute EOD liquidation state."""

    try:
        clock = retry_call(
            trading_client.get_clock,
            operation_name="get market clock",
        )
        current_time = _as_aware_datetime(_field(clock, "timestamp"), timezone.utc)
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        is_open = bool(_field(clock, "is_open", False))
        close_time = _calendar_close_for_current_session(trading_client, current_time)
        if close_time is None:
            close_time = _as_aware_datetime(_field(clock, "next_close"), timezone.utc)
    except Exception as exc:  # noqa: BLE001 - SDK and fake clients raise varied exceptions.
        raise OptionsTraderError(f"Unable to determine market session timing: {exc}") from exc

    return compute_market_session_timing(
        current_time=current_time,
        is_open=is_open,
        market_close_time=close_time,
        execution=execution,
    )


def compute_market_session_timing(
    *,
    current_time: datetime,
    is_open: bool,
    market_close_time: datetime | None,
    execution: ExecutionConfig,
) -> MarketSessionTiming:
    current = _as_aware_datetime(current_time, timezone.utc) or datetime.now(timezone.utc)
    close_time = _as_aware_datetime(market_close_time, EXCHANGE_TIMEZONE)
    minutes_until_close = None
    if close_time is not None:
        minutes_until_close = (
            close_time.astimezone(timezone.utc) - current.astimezone(timezone.utc)
        ).total_seconds() / 60.0

    liquidation_window_minutes = max(0, execution.liquidation_minutes_before_close)
    in_liquidation_window = (
        execution.close_positions_before_eod
        and is_open
        and minutes_until_close is not None
        and 0 <= minutes_until_close <= liquidation_window_minutes
    )
    return MarketSessionTiming(
        current_time=current,
        market_close_time=close_time,
        is_open=is_open,
        minutes_until_close=minutes_until_close,
        close_positions_before_eod=execution.close_positions_before_eod,
        liquidation_minutes_before_close=liquidation_window_minutes,
        in_liquidation_window=in_liquidation_window,
    )


def _calendar_close_for_current_session(
    trading_client: Any,
    current_time: datetime,
) -> datetime | None:
    try:
        from alpaca.trading.requests import GetCalendarRequest
    except ImportError as exc:
        raise OptionsTraderError("alpaca-py is not installed. Run: pip install alpaca-py") from exc

    market_date = current_time.astimezone(EXCHANGE_TIMEZONE).date()
    calendar = retry_call(
        lambda: trading_client.get_calendar(
            GetCalendarRequest(start=market_date, end=market_date)
        ),
        operation_name="get market calendar",
    )
    items = _calendar_items(calendar)
    if not items:
        return None
    return _as_aware_datetime(_field(items[0], "close"), EXCHANGE_TIMEZONE)


def _calendar_items(calendar: Any) -> list[Any]:
    if isinstance(calendar, dict):
        data = calendar.get("calendar") or calendar.get("calendars") or calendar.get("items") or []
        return list(data)
    if isinstance(calendar, list):
        return calendar
    return list(calendar or [])


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_aware_datetime(value: Any, default_timezone: timezone | ZoneInfo) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=default_timezone)
    return value
