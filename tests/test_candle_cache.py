from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import json
import time

from domain.entities.candle import Candle
from domain.value_objects.timeframe import Timeframe
from infrastructure.storage.cache.candle_cache import CandleCache
from interfaces.controllers.market_data_controller import MarketDataController


def test_candle_cache_round_trip(tmp_path: Path):
    cache_file = tmp_path / "candles.json"
    cache = CandleCache(cache_file=cache_file)

    assert cache_file.exists()

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


class _FakeFetchLatest:
    def __init__(self, candles: list[Candle]) -> None:
        self.candles = candles
        self.calls = 0

    def execute(self, *args, **kwargs):
        self.calls += 1
        return list(self.candles)


class _FakeFetchHistorical:
    def execute(self, *args, **kwargs):
        return []


def test_market_data_controller_rewrites_cache_each_request(tmp_path: Path):
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
    fetch_latest = _FakeFetchLatest([candle])
    controller = MarketDataController(
        fetch_latest=fetch_latest,
        fetch_historical=_FakeFetchHistorical(),
        candle_cache=cache,
    )

    controller.latest(symbol="TEST", timeframe=Timeframe.ONE_MINUTE, count=1)
    first_cache = json.loads(cache_file.read_text())
    first_stored_at = first_cache[next(iter(first_cache))]["stored_at"]
    assert fetch_latest.calls == 1

    time.sleep(0.001)
    controller.latest(symbol="TEST", timeframe=Timeframe.ONE_MINUTE, count=1)
    second_cache = json.loads(cache_file.read_text())
    second_stored_at = second_cache[next(iter(second_cache))]["stored_at"]

    assert fetch_latest.calls == 1  # second call used cache
    assert second_stored_at != first_stored_at  # cache rewritten on new request
