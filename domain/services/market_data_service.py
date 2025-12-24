from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from domain.entities.candle import Candle
from domain.value_objects.timeframe import Timeframe


class MarketDataService(ABC):
    """Abstract service for retrieving market data."""

    @abstractmethod
    def get_latest_ohlcv(
        self, symbol: str, timeframe: Timeframe, count: int = 1
    ) -> Sequence[Candle]:
        """Fetch the latest OHLCV candles for a symbol."""

    @abstractmethod
    def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[Candle]:
        """Fetch historical OHLCV candles for a symbol within a window."""
