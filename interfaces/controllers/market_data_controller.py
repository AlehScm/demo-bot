from __future__ import annotations

from datetime import datetime
from typing import Sequence

from application.use_cases.fetch_historical_ohlcv import FetchHistoricalOHLCV
from application.use_cases.fetch_latest_ohlcv import FetchLatestOHLCV
from domain.entities.candle import Candle
from domain.value_objects.timeframe import Timeframe
from infrastructure.storage.cache.candle_cache import CandleCache


class MarketDataController:
    """Controller that coordinates market data use cases."""

    def __init__(
        self,
        fetch_latest: FetchLatestOHLCV,
        fetch_historical: FetchHistoricalOHLCV,
        candle_cache: CandleCache | None = None,
    ) -> None:
        self.fetch_latest = fetch_latest
        self.fetch_historical = fetch_historical
        self.candle_cache = candle_cache

    def latest(self, symbol: str, timeframe: Timeframe, count: int = 1) -> Sequence[Candle]:
        if self.candle_cache:
            cached = self.candle_cache.get(symbol=symbol, timeframe=timeframe, count=count)
            if cached:
                return cached

        candles = list(self.fetch_latest.execute(symbol=symbol, timeframe=timeframe, count=count))

        if self.candle_cache and candles:
            self.candle_cache.set(symbol=symbol, timeframe=timeframe, count=count, candles=candles)

        return candles

    def historical(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[Candle]:
        return self.fetch_historical.execute(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )
