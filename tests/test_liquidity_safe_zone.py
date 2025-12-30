from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from domain.entities.candle import Candle
from domain.indicators.liquidity import LiquidityIndicator, LiquidityIndicatorSettings
from domain.value_objects.timeframe import Timeframe


def _build_candle(ts: datetime, low: str, high: str, close: str) -> Candle:
    return Candle(
        symbol="TEST",
        timeframe=Timeframe.ONE_MINUTE,
        timestamp=ts,
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1"),
    )


def _base_settings() -> LiquidityIndicatorSettings:
    return LiquidityIndicatorSettings(
        min_candles_in_zone=6,
        max_range_percent=Decimal("15"),
        min_strength=0.01,
        min_boundary_touches=1,
        max_zones=3,
        min_gap_between_zones=0,
        safe_zone_percent=Decimal("1"),
    )


def _build_base_candles(start: datetime) -> list[Candle]:
    candles: list[Candle] = []
    for i in range(12):
        ts = start + timedelta(minutes=i)
        candles.append(_build_candle(ts, "100", "110", "105"))
    return candles


def test_safe_zone_extends_boundaries_without_invalidation():
    indicator = LiquidityIndicator(settings=_base_settings())
    start = datetime(2024, 1, 1, 0, 0)
    candles = _build_base_candles(start)
    candles.append(_build_candle(start + timedelta(minutes=12), "100", "110.05", "110.05"))

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]
    assert zone.safe_zone_high == Decimal("110.1")
    assert zone.safe_zone_low == Decimal("99.9")
    assert zone.is_active
    assert zone.invalidated_at is None


def test_accumulation_only_closes_after_safe_zone_break():
    indicator = LiquidityIndicator(settings=_base_settings())
    start = datetime(2024, 1, 1, 0, 0)
    candles = _build_base_candles(start)
    candles.append(_build_candle(start + timedelta(minutes=12), "100", "110.05", "110.05"))
    breakout_candle = _build_candle(start + timedelta(minutes=13), "111", "112", "111.5")
    candles.append(breakout_candle)

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]
    assert not zone.is_active
    assert zone.invalidated_at == breakout_candle.timestamp
