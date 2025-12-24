from __future__ import annotations

from datetime import datetime
from typing import Sequence

from application.use_cases.fetch_historical_ohlcv import FetchHistoricalOHLCV
from application.use_cases.fetch_latest_ohlcv import FetchLatestOHLCV
from domain.entities.candle import Candle
from domain.value_objects.timeframe import Timeframe


class MarketDataController:
    """Controller that coordinates market data use cases."""

    def __init__(
        self,
        fetch_latest: FetchLatestOHLCV,
        fetch_historical: FetchHistoricalOHLCV,
    ) -> None:
        self.fetch_latest = fetch_latest
        self.fetch_historical = fetch_historical

    def latest(self, symbol: str, timeframe: Timeframe, count: int = 1) -> Sequence[Candle]:
        return self.fetch_latest.execute(symbol=symbol, timeframe=timeframe, count=count)

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
