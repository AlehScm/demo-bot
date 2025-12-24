from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TrendDirection(str, Enum):
    """Directional classification for price action."""

    UP = "UP"
    DOWN = "DOWN"
    SIDEWAYS = "SIDEWAYS"
    UNDEFINED = "UNDEFINED"

    @classmethod
    def undefined(cls) -> "TrendDirection":
        """Return a consistent undefined direction value."""

        return cls.UNDEFINED


class SwingType(str, Enum):
    """Type of swing pivot."""

    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True)
class Swing:
    """Represents a pivot swing extracted from price action."""

    index: int
    price: Decimal
    timestamp: datetime
    type: SwingType


@dataclass(frozen=True)
class TrendResult:
    """Standard output for the trend detector."""

    trend: TrendDirection
    confidence: float
    last_swings: list[Swing]
    reason: str
