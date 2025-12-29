"""
Liquidity Indicator for detecting accumulation zones.

Implements simplified Wyckoff accumulation detection by identifying
price ranges where the market is consolidating (moving sideways).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from domain.entities.candle import Candle
from domain.indicators.base import Indicator
from domain.indicators.liquidity.models import (
    AccumulationZone,
    LiquiditySignal,
    ZoneType,
)


@dataclass
class LiquidityIndicatorSettings:
    """Configuration for the liquidity indicator."""

    # Minimum candles to consider as accumulation zone
    min_candles_in_zone: int = 25
    
    # Maximum price range as percentage of average price to be considered consolidation
    # Tighter = more selective (0.8% is quite tight)
    max_range_percent: Decimal = Decimal("0.8")
    
    # Minimum zone strength to report (0.0 to 1.0)
    min_strength: float = 0.55
    
    # Minimum touches on support/resistance to confirm accumulation
    min_boundary_touches: int = 3
    
    # Maximum zones to return (most significant ones)
    max_zones: int = 5
    
    # Minimum gap between zones (in candles) to avoid clustering
    min_gap_between_zones: int = 15


class LiquidityIndicator(Indicator[LiquiditySignal]):
    """
    Liquidity indicator based on Wyckoff accumulation concepts.

    Identifies zones where price is consolidating in a tight range,
    indicating potential accumulation before a breakout.

    Detection Logic:
    1. Scan through candles using a sliding window
    2. For each window, calculate high/low range
    3. If range is below threshold % of average price = potential zone
    4. Verify multiple touches on boundaries (support/resistance)
    5. Check for true sideways movement (not trending)
    6. Merge overlapping zones and return top N strongest
    """

    def __init__(self, settings: LiquidityIndicatorSettings | None = None) -> None:
        self._settings = settings or LiquidityIndicatorSettings()
        self._zones: list[AccumulationZone] = []

    @property
    def name(self) -> str:
        return "LiquidityIndicator"

    @property
    def zones(self) -> list[AccumulationZone]:
        """Get detected accumulation zones."""
        return list(self._zones)

    def reset(self) -> None:
        """Reset the indicator state."""
        self._zones.clear()

    def analyze(self, candles: Sequence[Candle]) -> LiquiditySignal:
        """
        Analyze candles to detect accumulation zones.

        Args:
            candles: Sequence of OHLCV candles to analyze (oldest first).

        Returns:
            LiquiditySignal with detected accumulation zones.
        """
        if len(candles) < self._settings.min_candles_in_zone:
            return LiquiditySignal(
                accumulation_zones=[],
                total_zones=0,
                analysis_period_start=candles[0].timestamp if candles else None,
                analysis_period_end=candles[-1].timestamp if candles else None,
            )

        # Detect raw zones using sliding window
        raw_zones = self._detect_accumulation_zones(candles)

        # Merge overlapping zones
        merged_zones = self._merge_overlapping_zones(raw_zones)

        # Filter by minimum strength
        filtered_zones = [
            zone for zone in merged_zones
            if zone.strength >= self._settings.min_strength
        ]

        # Sort by strength and keep only top N
        filtered_zones.sort(key=lambda z: z.strength, reverse=True)
        filtered_zones = filtered_zones[:self._settings.max_zones]

        # Re-sort by time for display
        filtered_zones.sort(key=lambda z: z.start_time)

        self._zones = filtered_zones

        return LiquiditySignal(
            accumulation_zones=filtered_zones,
            total_zones=len(filtered_zones),
            analysis_period_start=candles[0].timestamp,
            analysis_period_end=candles[-1].timestamp,
        )

    def _detect_accumulation_zones(
        self, candles: Sequence[Candle]
    ) -> list[AccumulationZone]:
        """
        Detect accumulation zones using sliding window approach.
        """
        zones: list[AccumulationZone] = []
        min_window = self._settings.min_candles_in_zone
        max_window = min(len(candles) // 2, min_window * 4)
        
        # Use larger step to avoid too many similar zones
        step = max(min_window // 3, 8)
        
        for window_size in range(min_window, max_window + 1, 10):
            for start_idx in range(0, len(candles) - window_size + 1, step):
                end_idx = start_idx + window_size
                window = candles[start_idx:end_idx]
                
                zone = self._analyze_window(window, start_idx)
                if zone is not None:
                    zones.append(zone)

        return zones

    def _analyze_window(
        self, window: Sequence[Candle], start_idx: int
    ) -> AccumulationZone | None:
        """
        Analyze a window of candles to determine if it's an accumulation zone.
        """
        if len(window) < self._settings.min_candles_in_zone:
            return None

        # Calculate range
        high_price = max(c.high for c in window)
        low_price = min(c.low for c in window)
        range_size = high_price - low_price

        # Calculate average price
        avg_price = sum(c.close for c in window) / len(window)
        
        if avg_price == 0:
            return None

        # Calculate range as percentage of average price
        range_percent = (range_size / avg_price) * 100

        # Check if range is tight enough for accumulation
        if range_percent > self._settings.max_range_percent:
            return None

        # Check for true sideways movement (not trending)
        if not self._is_sideways(window):
            return None

        # Count boundary touches (support/resistance tests)
        touches = self._count_boundary_touches(window, high_price, low_price)
        if touches < self._settings.min_boundary_touches:
            return None

        # Calculate strength
        strength = self._calculate_zone_strength(window, range_percent, touches)

        return AccumulationZone(
            start_time=window[0].timestamp,
            end_time=window[-1].timestamp,
            high_price=high_price,
            low_price=low_price,
            candle_count=len(window),
            strength=strength,
            zone_type=ZoneType.ACCUMULATION,
        )

    def _is_sideways(self, window: Sequence[Candle]) -> bool:
        """
        Check if the price action is truly sideways (not trending).
        
        Compares the start, middle, and end prices to ensure no clear trend.
        """
        if len(window) < 6:
            return False

        # Divide window into thirds
        third = len(window) // 3
        
        start_prices = [c.close for c in window[:third]]
        mid_prices = [c.close for c in window[third:2*third]]
        end_prices = [c.close for c in window[2*third:]]
        
        start_avg = sum(start_prices) / len(start_prices)
        mid_avg = sum(mid_prices) / len(mid_prices)
        end_avg = sum(end_prices) / len(end_prices)
        
        # Calculate overall average
        overall_avg = (start_avg + mid_avg + end_avg) / 3
        
        if overall_avg == 0:
            return False
        
        # Check if all thirds are within 0.5% of overall average
        threshold = Decimal("0.005")  # 0.5%
        
        start_dev = abs(start_avg - overall_avg) / overall_avg
        mid_dev = abs(mid_avg - overall_avg) / overall_avg
        end_dev = abs(end_avg - overall_avg) / overall_avg
        
        return (
            start_dev < threshold and
            mid_dev < threshold and
            end_dev < threshold
        )

    def _count_boundary_touches(
        self, window: Sequence[Candle], high: Decimal, low: Decimal
    ) -> int:
        """
        Count how many times price touches the upper or lower boundary.
        
        A touch is when the candle's high/low is within 0.2% of the boundary.
        """
        range_size = high - low
        if range_size == 0:
            return 0
        
        # Touch threshold: within 15% of the range from the boundary
        touch_threshold = range_size * Decimal("0.15")
        
        upper_touches = 0
        lower_touches = 0
        
        for candle in window:
            # Check upper boundary touch
            if high - candle.high <= touch_threshold:
                upper_touches += 1
            
            # Check lower boundary touch
            if candle.low - low <= touch_threshold:
                lower_touches += 1
        
        # We want both boundaries to be tested
        return min(upper_touches, lower_touches)

    def _calculate_zone_strength(
        self, window: Sequence[Candle], range_percent: Decimal, touches: int
    ) -> float:
        """
        Calculate the strength of an accumulation zone.
        
        Strength is based on:
        - Tighter range = stronger (max contribution: 0.3)
        - More candles = stronger (max contribution: 0.2)
        - More boundary touches = stronger (max contribution: 0.3)
        - Price concentration near middle = stronger (max contribution: 0.2)
        """
        # Range tightness factor (tighter = better)
        max_range = float(self._settings.max_range_percent)
        range_factor = 1.0 - (float(range_percent) / max_range)
        range_contribution = range_factor * 0.3

        # Candle count factor
        min_candles = self._settings.min_candles_in_zone
        max_bonus_candles = min_candles * 3
        candle_factor = min(
            (len(window) - min_candles) / (max_bonus_candles - min_candles),
            1.0
        )
        candle_contribution = max(0, candle_factor) * 0.2

        # Boundary touches factor
        min_touches = self._settings.min_boundary_touches
        max_touches = min_touches * 3
        touch_factor = min((touches - min_touches) / (max_touches - min_touches), 1.0)
        touch_contribution = max(0, touch_factor) * 0.3

        # Price concentration factor (how much price stays near middle)
        mid_price = (max(c.high for c in window) + min(c.low for c in window)) / 2
        deviations = [
            abs(c.close - mid_price) / mid_price if mid_price > 0 else Decimal(0)
            for c in window
        ]
        avg_deviation = sum(deviations) / len(deviations) if deviations else Decimal(0)
        concentration_factor = 1.0 - min(float(avg_deviation) * 20, 1.0)
        concentration_contribution = max(0, concentration_factor) * 0.2

        return min(
            range_contribution + candle_contribution + touch_contribution + concentration_contribution,
            1.0
        )

    def _merge_overlapping_zones(
        self, zones: list[AccumulationZone]
    ) -> list[AccumulationZone]:
        """
        Merge zones that overlap significantly.
        """
        if not zones:
            return []

        # Sort by start time
        sorted_zones = sorted(zones, key=lambda z: z.start_time)
        merged: list[AccumulationZone] = []

        for zone in sorted_zones:
            if not merged:
                merged.append(zone)
                continue

            last = merged[-1]
            
            # Check for time overlap (more than 50% overlap)
            overlap_start = max(last.start_time, zone.start_time)
            overlap_end = min(last.end_time, zone.end_time)
            
            if overlap_start < overlap_end:
                # Calculate overlap percentage
                zone_duration = (zone.end_time - zone.start_time).total_seconds()
                overlap_duration = (overlap_end - overlap_start).total_seconds()
                
                if zone_duration > 0 and overlap_duration / zone_duration > 0.5:
                    # Significant overlap - merge zones
                    # Check for price overlap too
                    price_overlap = (
                        zone.low_price <= last.high_price and
                        zone.high_price >= last.low_price
                    )
                    
                    if price_overlap:
                        # Keep the stronger zone or merge
                        if zone.strength > last.strength:
                            merged[-1] = zone
                        continue
            
            # Check minimum gap between zones
            gap = (zone.start_time - last.end_time).total_seconds()
            min_gap_seconds = self._settings.min_gap_between_zones * 60  # Assuming 1min candles
            
            if gap >= min_gap_seconds or zone.strength > last.strength * 1.2:
                merged.append(zone)

        return merged
