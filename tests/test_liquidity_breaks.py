from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from domain.entities.candle import Candle
from domain.indicators.liquidity import LiquidityIndicator, LiquidityIndicatorSettings
from domain.value_objects.timeframe import Timeframe


def _candle(ts: datetime, low: str, high: str, close: str = "100") -> Candle:
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
        max_range_percent=Decimal("5"),
        min_strength=0.01,
        min_boundary_touches=1,
        max_zones=5,
        min_gap_between_zones=1,
        seed_candles=6,
        break_invalid_pct=Decimal("0.2"),
        break_confirm_candles=2,
        sweep_tolerance_pct=Decimal("0.04"),
    )


def test_sweep_stays_inside_same_range():
    settings = _base_settings()
    indicator = LiquidityIndicator(settings=settings)

    start = datetime(2024, 1, 1, 0, 0)
    candles: list[Candle] = []

    # Seed window (tight range)
    for i in range(6):
        ts = start + timedelta(minutes=i)
        candles.append(_candle(ts, "99", "101"))

    # Sweep below range_low but close back inside (penetration < 20%)
    sweep_ts = start + timedelta(minutes=6)
    candles.append(_candle(sweep_ts, "98.7", "101"))

    # Inside candle
    inside_ts = start + timedelta(minutes=7)
    candles.append(_candle(inside_ts, "99.2", "100.8"))

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]
    assert zone.candle_count == 8
    assert zone.low_price == Decimal("98.7")
    assert zone.high_price == Decimal("101")


def test_penetration_break_ends_zone():
    settings = _base_settings()
    indicator = LiquidityIndicator(settings=settings)

    start = datetime(2024, 1, 1, 0, 0)
    candles: list[Candle] = []

    for i in range(6):
        ts = start + timedelta(minutes=i)
        candles.append(_candle(ts, "99", "101"))

    # Breaks more than 20% of range height and closes outside
    break_ts = start + timedelta(minutes=6)
    candles.append(_candle(break_ts, "98", "101.5", "98.5"))

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]
    # Break candle is excluded; zone ends on last seed candle
    assert zone.end_time == candles[5].timestamp
    assert zone.candle_count == 6
    assert zone.low_price == Decimal("99")
    assert zone.high_price == Decimal("101")


def test_consecutive_closes_outside_confirm_break():
    settings = _base_settings()
    indicator = LiquidityIndicator(settings=settings)

    start = datetime(2024, 1, 1, 0, 0)
    candles: list[Candle] = []

    for i in range(6):
        ts = start + timedelta(minutes=i)
        candles.append(_candle(ts, "99", "101"))

    # First small push above range_high (close outside but shallow penetration)
    push_ts = start + timedelta(minutes=6)
    candles.append(_candle(push_ts, "99.5", "101.1", "101.05"))

    # Second close outside confirms break
    confirm_ts = start + timedelta(minutes=7)
    candles.append(_candle(confirm_ts, "99.6", "101.2", "101.1"))

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]
    # Break confirmed on last candle; zone stops one candle earlier
    assert zone.end_time == candles[6].timestamp
    assert zone.candle_count == 7
    assert zone.high_price == Decimal("101.1")
    assert zone.low_price == Decimal("99")


def test_tiny_outside_close_does_not_break():
    settings = _base_settings()
    indicator = LiquidityIndicator(settings=settings)

    start = datetime(2024, 1, 1, 0, 0)
    candles: list[Candle] = []

    for i in range(6):
        ts = start + timedelta(minutes=i)
        candles.append(_candle(ts, "99", "101"))

    # Very shallow poke below (penetration ~2.5%) and closes slightly outside
    shallow_ts = start + timedelta(minutes=6)
    candles.append(_candle(shallow_ts, "98.95", "101", "98.97"))

    # Back inside
    back_ts = start + timedelta(minutes=7)
    candles.append(_candle(back_ts, "99.2", "100.8"))

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]
    assert zone.candle_count == 8
    assert zone.low_price == Decimal("98.95")
    assert zone.high_price == Decimal("101")
