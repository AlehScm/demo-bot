"""
Value objects for the liquidity indicator.

Contains data structures for accumulation zones, distribution zones,
and liquidity signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class ZoneType(str, Enum):
    """Type of liquidity zone."""

    ACCUMULATION = "ACCUMULATION"  # Price consolidating before potential breakout up
    DISTRIBUTION = "DISTRIBUTION"  # Price consolidating before potential breakdown


class LiquidityEventDirection(str, Enum):
    """Direction for sweeps or range breaks relative to the zone."""

    ABOVE = "ABOVE"  # Liquidity taken above the range high (BSL sweep)
    BELOW = "BELOW"  # Liquidity taken below the range low (SSL sweep)


@dataclass(frozen=True)
class LiquiditySweep:
    """Short-lived liquidity grab that returns inside the range (sweep/stop hunt)."""

    start_time: datetime
    end_time: datetime
    direction: LiquidityEventDirection
    penetration_percent: float
    candle_count: int


@dataclass(frozen=True)
class RangeBreak:
    """Range break that invalidates the accumulation zone."""

    start_time: datetime
    end_time: datetime
    start_index: int
    end_index: int
    direction: LiquidityEventDirection
    penetration_percent: float
    candle_count: int
    closes_outside: int


@dataclass(frozen=True)
class AccumulationZone:
    """
    Represents a Wyckoff-style accumulation/consolidation zone.

    This is a range where price has been trading sideways, indicating
    potential accumulation by smart money before a move.
    """

    start_time: datetime
    end_time: datetime
    high_price: Decimal
    low_price: Decimal
    candle_count: int
    strength: float  # 0.0 to 1.0 - how strong/clear the accumulation is
    zone_type: ZoneType = ZoneType.ACCUMULATION
    liquidity_sweeps: list[LiquiditySweep] = field(default_factory=list)
    range_break: RangeBreak | None = None

    @property
    def range_size(self) -> Decimal:
        """Calculate the price range of the zone."""
        return self.high_price - self.low_price

    @property
    def mid_price(self) -> Decimal:
        """Calculate the middle price of the zone."""
        return (self.high_price + self.low_price) / 2

    @property
    def range_percent(self) -> float:
        """Calculate the range as percentage of mid price."""
        if self.mid_price == 0:
            return 0.0
        return float(self.range_size / self.mid_price) * 100


@dataclass(frozen=True)
class LiquiditySignal:
    """
    Result of liquidity analysis containing detected zones.

    Contains all accumulation and distribution zones found in the analyzed data.
    """

    accumulation_zones: list[AccumulationZone] = field(default_factory=list)
    total_zones: int = 0
    analysis_period_start: datetime | None = None
    analysis_period_end: datetime | None = None

    @property
    def has_accumulation(self) -> bool:
        """Check if any accumulation zones were detected."""
        return len(self.accumulation_zones) > 0

    @property
    def strongest_zone(self) -> AccumulationZone | None:
        """Get the strongest accumulation zone by strength."""
        if not self.accumulation_zones:
            return None
        return max(self.accumulation_zones, key=lambda z: z.strength)

    @property
    def most_recent_zone(self) -> AccumulationZone | None:
        """Get the most recent accumulation zone."""
        if not self.accumulation_zones:
            return None
        return max(self.accumulation_zones, key=lambda z: z.end_time)
