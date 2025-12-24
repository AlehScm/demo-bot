from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Timeframe(str, Enum):
    ONE_MINUTE = "1min"
    FIVE_MINUTES = "5min"
    FIFTEEN_MINUTES = "15min"
    THIRTY_MINUTES = "30min"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1day"

    def to_twelvedata_interval(self) -> str:
        """Return the interval string expected by Twelve Data."""
        return self.value


@dataclass(frozen=True)
class Symbol:
    """Value object representing an asset symbol."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
