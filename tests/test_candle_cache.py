from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from domain.entities.candle import Candle
from domain.value_objects.timeframe import Timeframe
from infrastructure.storage.cache.candle_cache import CandleCache


def test_candle_cache_round_trip(tmp_path: Path):
    cache_file = tmp_path / "candles.json"
    cache = CandleCache(cache_file=cache_file)

    candle = Candle(
        symbol="TEST",
        timeframe=Timeframe.ONE_MINUTE,
        timestamp=datetime(2024, 1, 1, 0, 0),
        open=Decimal("1.0"),
        high=Decimal("1.1"),
        low=Decimal("0.9"),
        close=Decimal("1.05"),
        volume=Decimal("100"),
    )

    cache.set(symbol="TEST", timeframe=Timeframe.ONE_MINUTE, count=2, candles=[candle])

    loaded = cache.get(symbol="TEST", timeframe=Timeframe.ONE_MINUTE, count=2)

    assert loaded is not None
    assert loaded[0] == candle
