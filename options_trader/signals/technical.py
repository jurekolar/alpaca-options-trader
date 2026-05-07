"""Small, dependency-free technical indicators for intraday scans and backtests."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev


@dataclass(frozen=True)
class TechnicalSnapshot:
    rsi: float | None
    short_ma: float | None
    long_ma: float | None
    trend_score: float
    momentum_score: float
    volume_spike_score: float
    breakout_score: float
    realized_volatility: float | None
    vwap_deviation_pct: float | None


def _last(values: list[float], count: int) -> list[float]:
    return values[-count:] if len(values) >= count else []


def moving_average(values: list[float], window: int) -> float | None:
    chunk = _last(values, window)
    return mean(chunk) if chunk else None


def rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) < window + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, current in zip(values[-window - 1 : -1], values[-window:]):
        change = current - prev
        if change >= 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def realized_volatility(values: list[float], periods_per_year: int = 252 * 390) -> float | None:
    if len(values) < 3:
        return None
    returns = []
    for prev, current in zip(values[:-1], values[1:]):
        if prev > 0:
            returns.append((current / prev) - 1.0)
    if len(returns) < 2:
        return None
    return pstdev(returns) * sqrt(periods_per_year)


def compute_vwap(prices: list[float], volumes: list[int]) -> float | None:
    if not prices or not volumes or len(prices) != len(volumes):
        return None
    total_volume = sum(volumes)
    if total_volume <= 0:
        return None
    return sum(price * volume for price, volume in zip(prices, volumes)) / total_volume


def compute_technical_snapshot(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[int],
    short_window: int = 9,
    long_window: int = 21,
) -> TechnicalSnapshot:
    current = closes[-1] if closes else None
    rsi_value = rsi(closes)
    short_ma = moving_average(closes, short_window)
    long_ma = moving_average(closes, long_window)
    trend_score = 50.0
    if current and short_ma and long_ma:
        trend_score = 75.0 if current > short_ma > long_ma else 25.0 if current < short_ma < long_ma else 50.0

    momentum_score = 50.0
    if len(closes) >= 6 and closes[-6] > 0:
        change = (closes[-1] / closes[-6]) - 1.0
        momentum_score = max(0.0, min(100.0, 50.0 + change * 600.0))

    volume_spike_score = 50.0
    recent_volumes = _last([float(v) for v in volumes], 20)
    if recent_volumes and volumes:
        avg_volume = mean(recent_volumes)
        if avg_volume > 0:
            volume_spike_score = max(0.0, min(100.0, (volumes[-1] / avg_volume) * 50.0))

    breakout_score = 50.0
    prior_highs = highs[-21:-1] if len(highs) >= 21 else highs[:-1]
    prior_lows = lows[-21:-1] if len(lows) >= 21 else lows[:-1]
    if current and prior_highs and prior_lows:
        if current > max(prior_highs):
            breakout_score = 85.0
        elif current < min(prior_lows):
            breakout_score = 15.0

    vwap = compute_vwap(closes, volumes)
    vwap_deviation = ((current / vwap) - 1.0) if current and vwap and vwap > 0 else None
    return TechnicalSnapshot(
        rsi=rsi_value,
        short_ma=short_ma,
        long_ma=long_ma,
        trend_score=trend_score,
        momentum_score=momentum_score,
        volume_spike_score=volume_spike_score,
        breakout_score=breakout_score,
        realized_volatility=realized_volatility(closes),
        vwap_deviation_pct=vwap_deviation,
    )

