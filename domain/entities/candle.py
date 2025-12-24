from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain.value_objects.timeframe import Timeframe


@dataclass(frozen=True)
class Candle:
    """Represents an OHLCV candle for a specific symbol and timeframe."""

    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
