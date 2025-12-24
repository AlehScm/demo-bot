from __future__ import annotations

from datetime import datetime
from typing import Sequence

from application.policies.timeframe_policy import TimeframePolicy
from domain.entities.candle import Candle
from domain.services.market_data_service import MarketDataService
from domain.value_objects.timeframe import Timeframe


class FetchHistoricalOHLCV:
    """Use case to fetch historical OHLCV candles."""

    def __init__(
        self,
        market_data_service: MarketDataService,
        timeframe_policy: TimeframePolicy,
    ) -> None:
        self.market_data_service = market_data_service
        self.timeframe_policy = timeframe_policy

    def execute(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[Candle]:
        validated_timeframe = self.timeframe_policy.ensure_supported(timeframe)
        return self.market_data_service.get_historical_ohlcv(
            symbol=symbol,
            timeframe=validated_timeframe,
            start=start,
            end=end,
            limit=limit,
        )
