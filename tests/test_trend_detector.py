from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from domain.entities.candle import Candle
from domain.services.trend_detector import SwingSettings, TrendDetector
from domain.value_objects.timeframe import Timeframe
from domain.value_objects.trend import SwingType, TrendDirection


def make_candle(base_time: datetime, idx: int, open_: str, high: str, low: str, close: str) -> Candle:
    return Candle(
        symbol="TEST",
        timeframe=Timeframe.ONE_MINUTE,
        timestamp=base_time + timedelta(minutes=idx),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1000"),
    )


def test_uptrend_detects_higher_high_and_higher_low():
    base_time = datetime.utcnow()
    candles = [
        make_candle(base_time, 0, "100", "101", "99", "100"),
        make_candle(base_time, 1, "101", "105", "100", "104"),
        make_candle(base_time, 2, "103", "103", "97", "98"),
        make_candle(base_time, 3, "99", "110", "104", "109"),
        make_candle(base_time, 4, "105", "108", "102", "103"),
        make_candle(base_time, 5, "104", "120", "107", "118"),
    ]

    detector = TrendDetector(SwingSettings(min_percent_move=Decimal("0.01")))
    result = detector.analyze(candles)

    assert result.trend is TrendDirection.UP
    assert result.confidence > 0.5
    highs = [s for s in result.last_swings if s.type is SwingType.HIGH]
    lows = [s for s in result.last_swings if s.type is SwingType.LOW]
    assert len(highs) >= 2 and len(lows) >= 2


def test_downtrend_detects_lower_high_and_lower_low():
    base_time = datetime.utcnow()
    candles = [
        make_candle(base_time, 0, "120", "121", "118", "119"),
        make_candle(base_time, 1, "119", "119", "112", "113"),
        make_candle(base_time, 2, "113", "114", "109", "110"),
        make_candle(base_time, 3, "110", "110", "102", "103"),
        make_candle(base_time, 4, "103", "104", "95", "96"),
        make_candle(base_time, 5, "95", "97", "90", "91"),
    ]

    detector = TrendDetector(SwingSettings(min_percent_move=Decimal("0.01")))
    result = detector.analyze(candles)

    assert result.trend is TrendDirection.DOWN
    assert result.confidence > 0.5


def test_noise_is_filtered_and_trend_is_undefined():
    base_time = datetime.utcnow()
    candles = [
        make_candle(base_time, 0, "100", "101", "99", "100"),
        make_candle(base_time, 1, "100", "101.1", "99.5", "100.5"),
        make_candle(base_time, 2, "100", "101.2", "99.6", "100.4"),
        make_candle(base_time, 3, "100", "101.15", "99.4", "100.2"),
    ]

    detector = TrendDetector(SwingSettings(min_percent_move=Decimal("0.05")))
    result = detector.analyze(candles)

    assert result.trend is TrendDirection.UNDEFINED
    assert result.confidence <= 0.25
    assert result.last_swings == []
    assert "undefined" in result.reason.lower()
