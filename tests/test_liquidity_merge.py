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


def test_adjacent_zones_merge_into_single_region():
    """
    Two near-adjacent consolidations with overlapping price should merge
    into one extended accumulation zone.
    """
    settings = LiquidityIndicatorSettings(
        min_candles_in_zone=3,
        max_range_percent=Decimal("5"),
        min_strength=0.01,
        min_boundary_touches=1,
        max_zones=5,
        min_gap_between_zones=5,
    )
    indicator = LiquidityIndicator(settings=settings)

    start = datetime(2024, 1, 1, 0, 0)
    candles: list[Candle] = []

    # First tight range
    for i in range(6):
        ts = start + timedelta(minutes=i)
        candles.append(_build_candle(ts, "99", "101", "100"))

    # Small gap then another tight range with overlapping prices
    gap_ts = start + timedelta(minutes=7)
    for i in range(6):
        ts = gap_ts + timedelta(minutes=i)
        candles.append(_build_candle(ts, "98.8", "101.2", "100"))

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]
    assert zone.start_time == candles[0].timestamp
    assert zone.end_time >= candles[-1].timestamp - timedelta(minutes=1)
