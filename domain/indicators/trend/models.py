"""
Value objects for the trend indicator.

Contains data structures for swing points, break of structure (BOS),
and trend signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class SwingClassification(str, Enum):
    """Classification of swing points based on market structure."""

    HIGHER_HIGH = "HH"  # Higher High - bullish continuation
    HIGHER_LOW = "HL"  # Higher Low - bullish continuation
    LOWER_LOW = "LL"  # Lower Low - bearish continuation
    LOWER_HIGH = "LH"  # Lower High - bearish continuation
    SWING_HIGH = "SH"  # Unclassified swing high
    SWING_LOW = "SL"  # Unclassified swing low


class BOSType(str, Enum):
    """Type of Break of Structure."""

    BULLISH = "BULLISH"  # Price breaks above swing high - bullish continuation
    BEARISH = "BEARISH"  # Price breaks below swing low - bearish continuation


class TrendDirection(str, Enum):
    """Direction of the market trend."""

    UP = "UP"
    DOWN = "DOWN"
    UNDEFINED = "UNDEFINED"


@dataclass(frozen=True)
class SwingPoint:
    """
    Represents a swing point in the market structure.

    A swing point is a local high or low that represents a significant
    turning point in price action.
    """

    price: Decimal
    timestamp: datetime
    index: int
    classification: SwingClassification

    @property
    def is_high(self) -> bool:
        """Check if this is a swing high."""
        return self.classification in (
            SwingClassification.HIGHER_HIGH,
            SwingClassification.LOWER_HIGH,
            SwingClassification.SWING_HIGH,
        )

    @property
    def is_low(self) -> bool:
        """Check if this is a swing low."""
        return self.classification in (
            SwingClassification.HIGHER_LOW,
            SwingClassification.LOWER_LOW,
            SwingClassification.SWING_LOW,
        )


@dataclass(frozen=True)
class BreakOfStructure:
    """
    Represents a Break of Structure (BOS) event.

    BOS occurs when price breaks a significant swing point,
    confirming trend continuation.
    """

    type: BOSType
    broken_swing: SwingPoint
    break_price: Decimal
    break_timestamp: datetime
    break_index: int

    @property
    def is_bullish(self) -> bool:
        """Check if this is a bullish BOS."""
        return self.type == BOSType.BULLISH

    @property
    def is_bearish(self) -> bool:
        """Check if this is a bearish BOS."""
        return self.type == BOSType.BEARISH


@dataclass(frozen=True)
class TrendSignal:
    """
    Result of trend analysis containing market structure information.

    Contains the detected trend direction, classified swing points,
    and any detected break of structure events.
    """

    trend: TrendDirection
    swings: list[SwingPoint] = field(default_factory=list)
    last_bos: BreakOfStructure | None = None
    confidence: float = 0.0
    reason: str = ""

    @property
    def is_bullish(self) -> bool:
        """Check if the trend is bullish (up)."""
        return self.trend == TrendDirection.UP

    @property
    def is_bearish(self) -> bool:
        """Check if the trend is bearish (down)."""
        return self.trend == TrendDirection.DOWN

    @property
    def is_undefined(self) -> bool:
        """Check if the trend is undefined."""
        return self.trend == TrendDirection.UNDEFINED

