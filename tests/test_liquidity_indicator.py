from datetime import datetime, timedelta
from decimal import Decimal

from domain.entities.candle import Candle
from domain.indicators.liquidity import LiquidityIndicator
from domain.value_objects.timeframe import Timeframe


def _make_candle(index: int, open_: str, high: str, low: str, close: str, volume: str) -> Candle:
    """
    Helper to build deterministic candles using strings to avoid floating errors.
    """
    base_time = datetime(2024, 1, 1)
    return Candle(
        symbol="TEST",
        timeframe=Timeframe.ONE_MINUTE,
        timestamp=base_time + timedelta(minutes=index),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
    )


def _wyckoff_accumulation_sequence() -> list[Candle]:
    """
    Build a simplified Wyckoff accumulation with PS, SC, AR, STs and Spring.
    """
    candles: list[Candle] = []
    price = Decimal("105")
    index = 0

    # Downtrend into the range
    for _ in range(12):
        open_ = price
        close = price - Decimal("0.6")
        high = open_ + Decimal("0.2")
        low = close - Decimal("0.4")
        candles.append(_make_candle(index, str(open_), str(high), str(low), str(close), "90"))
        price = close
        index += 1

    # Preliminary Support
    candles.append(_make_candle(index, "97.8", "98.2", "96.5", "96.9", "150"))
    index += 1

    # Selling Climax with spike in volume and range
    candles.append(_make_candle(index, "96.8", "98.0", "95.4", "95.7", "230"))
    index += 1

    # Automatic Rally forming resistance
    candles.append(_make_candle(index, "95.8", "98.8", "95.5", "98.4", "170"))
    index += 1

    # Secondary Tests with contracting volume near support
    candles.append(_make_candle(index, "98.0", "96.6", "95.5", "96.2", "120"))
    index += 1
    candles.append(_make_candle(index, "96.1", "96.7", "95.6", "96.3", "110"))
    index += 1

    # Spring/Shakeout
    candles.append(_make_candle(index, "96.4", "96.6", "94.9", "95.6", "140"))
    index += 1

    # Consolidation after Spring
    consolidation = [
        ("96.0", "97.1", "95.7", "96.8", "105"),
        ("96.7", "97.0", "95.9", "96.4", "100"),
        ("96.4", "97.2", "96.0", "96.9", "102"),
        ("96.8", "97.5", "96.3", "97.2", "108"),
        ("97.0", "97.6", "96.5", "97.4", "112"),
        ("97.5", "97.8", "96.9", "97.6", "115"),
    ]
    for open_, high, low, close, volume in consolidation:
        candles.append(_make_candle(index, open_, high, low, close, volume))
        index += 1

    # Pad to exceed min_candles_in_zone
    while len(candles) < 30:
        candles.append(_make_candle(index, "97.4", "97.9", "96.9", "97.2", "95"))
        index += 1

    return candles


def test_detects_wyckoff_accumulation_with_spring() -> None:
    indicator = LiquidityIndicator()
    candles = _wyckoff_accumulation_sequence()

    signal = indicator.analyze(candles)

    assert signal.total_zones == 1
    zone = signal.accumulation_zones[0]

    assert zone.candle_count >= indicator._settings.min_candles_in_zone
    assert zone.low_price < Decimal("96")
    assert zone.high_price > Decimal("98")
    assert zone.strength >= indicator._settings.min_strength


def test_returns_empty_when_no_downtrend() -> None:
    indicator = LiquidityIndicator()

    candles = []
    index = 0
    price = Decimal("100")
    for _ in range(30):
        candles.append(
            _make_candle(
                index,
                str(price),
                str(price + Decimal("0.3")),
                str(price - Decimal("0.3")),
                str(price + Decimal("0.1")),
                "80",
            )
        )
        price += Decimal("0.2")
        index += 1

    signal = indicator.analyze(candles)

    assert signal.total_zones == 0
