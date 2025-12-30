"""
Liquidity Indicator for detecting accumulation zones.

Implements simplified Wyckoff accumulation detection by identifying
price ranges where the market is consolidating (moving sideways).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from domain.entities.candle import Candle
from domain.indicators.base import Indicator
from domain.indicators.liquidity.models import (
    AccumulationZone,
    LiquiditySignal,
    ZoneType,
)
from domain.indicators.liquidity.settings import LiquidityIndicatorSettings


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
    6. Extends the zone forward until a sweep or range break occurs using
       penetration thresholds
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
        if len(candles) < self._settings.seed_candles:
            return LiquiditySignal(
                accumulation_zones=[],
                total_zones=0,
                analysis_period_start=candles[0].timestamp if candles else None,
                analysis_period_end=candles[-1].timestamp if candles else None,
            )

        # Detect raw zones using seed + extension logic
        raw_zones = self._detect_accumulation_zones(candles)

        # Filter by minimum strength
        filtered_zones = [
            zone for zone in raw_zones
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
        Detect accumulation zones using a seed-window approach with sweep/break logic.
        """
        zones: list[AccumulationZone] = []
        idx = 0
        seed = self._settings.seed_candles

        while idx + seed <= len(candles):
            window = candles[idx : idx + seed]
            seed_info = self._evaluate_seed_window(window)

            if seed_info is None:
                idx += 1
                continue

            range_low, range_high = seed_info
            end_idx, zone_high, zone_low, next_start = self._extend_zone(
                candles, idx, range_low, range_high
            )

            zone_candles = candles[idx : end_idx + 1]
            zone = self._build_zone(zone_candles, zone_low, zone_high)
            if zone is not None:
                zones.append(zone)

            if next_start <= idx:
                idx += 1
            else:
                idx = next_start

        return zones

    def _evaluate_seed_window(
        self, window: Sequence[Candle]
    ) -> tuple[Decimal, Decimal] | None:
        """
        Validate a seed window and return its initial range (low, high).
        """
        if len(window) < self._settings.seed_candles:
            return None

        high_price = max(c.high for c in window)
        low_price = min(c.low for c in window)
        range_size = high_price - low_price

        if range_size <= 0:
            return None

        avg_price = sum(c.close for c in window) / len(window)
        if avg_price == 0:
            return None

        range_percent = (range_size / avg_price) * 100
        if range_percent > self._settings.max_range_percent:
            return None

        if not self._is_sideways(window):
            return None

        touches = self._count_boundary_touches(window, high_price, low_price)
        if touches < self._settings.min_boundary_touches:
            return None

        return low_price, high_price

    def _extend_zone(
        self,
        candles: Sequence[Candle],
        start_idx: int,
        range_low: Decimal,
        range_high: Decimal,
    ) -> tuple[int, Decimal, Decimal, int]:
        """
        Extend a validated seed zone forward until a confirmed break occurs.

        Returns:
            end_idx: index of last candle considered part of the zone
            zone_high: highest high inside the zone (including sweeps)
            zone_low: lowest low inside the zone (including sweeps)
            next_start_idx: index where next search should resume (break candle)
        """
        range_height = range_high - range_low
        if range_height <= 0:
            seed_end = start_idx + self._settings.seed_candles - 1
            return seed_end, range_high, range_low, seed_end + 1

        zone_high = range_high
        zone_low = range_low
        end_idx = start_idx + self._settings.seed_candles - 1
        next_start_idx = end_idx + 1
        outside_closes = 0

        for idx in range(end_idx + 1, len(candles)):
            candle = candles[idx]
            breach_high = candle.high > range_high
            breach_low = candle.low < range_low

            if not breach_high and not breach_low:
                outside_closes = 0
                zone_high = max(zone_high, candle.high)
                zone_low = min(zone_low, candle.low)
                end_idx = idx
                next_start_idx = idx + 1
                continue

            penetration_up = (candle.high - range_high) / range_height if breach_high else Decimal("0")
            penetration_down = (range_low - candle.low) / range_height if breach_low else Decimal("0")
            penetration = max(penetration_up, penetration_down)

            close_inside = range_low <= candle.close <= range_high
            close_outside = candle.close < range_low or candle.close > range_high

            if penetration <= self._settings.sweep_tolerance_pct:
                # Very small poke through the range: treat as sweep regardless of close
                outside_closes = 0
                zone_high = max(zone_high, candle.high)
                zone_low = min(zone_low, candle.low)
                end_idx = idx
                next_start_idx = idx + 1
                continue

            if penetration < self._settings.break_invalid_pct and close_inside:
                # Sweep: reject and return into range
                outside_closes = 0
                zone_high = max(zone_high, candle.high)
                zone_low = min(zone_low, candle.low)
                end_idx = idx
                next_start_idx = idx + 1
                continue

            if close_outside:
                outside_closes += 1
            else:
                outside_closes = 0

            if penetration >= self._settings.break_invalid_pct or outside_closes >= self._settings.break_confirm_candles:
                # Confirmed break: stop before this candle
                next_start_idx = idx
                break

            # Soft penetration but not a confirmed break: keep extending the box
            zone_high = max(zone_high, candle.high)
            zone_low = min(zone_low, candle.low)
            end_idx = idx
            next_start_idx = idx + 1

        return end_idx, zone_high, zone_low, next_start_idx

    def _build_zone(
        self,
        window: Sequence[Candle],
        low_price: Decimal,
        high_price: Decimal,
    ) -> AccumulationZone | None:
        """Construct a zone object after validation."""
        if len(window) < self._settings.min_candles_in_zone:
            return None

        range_size = high_price - low_price
        if range_size <= 0:
            return None

        avg_price = sum(c.close for c in window) / len(window)
        if avg_price == 0:
            return None

        range_percent = (range_size / avg_price) * 100
        if range_percent > self._settings.max_range_percent:
            return None

        if not self._is_sideways(window):
            return None

        touches = self._count_boundary_touches(window, high_price, low_price)
        if touches < self._settings.min_boundary_touches:
            return None

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

    def _zones_can_merge(self, left: AccumulationZone, right: AccumulationZone) -> bool:
        """Check if two zones should be merged (overlap or very close with similar price ranges)."""
        overlap_start = max(left.start_time, right.start_time)
        overlap_end = min(left.end_time, right.end_time)

        # Time overlap or very small gap
        gap_seconds = max((right.start_time - left.end_time).total_seconds(), 0)
        min_gap_seconds = self._settings.min_gap_between_zones * 60
        time_close_enough = overlap_start < overlap_end or gap_seconds <= min_gap_seconds

        # Price overlap or near-overlap (allow 10% buffer of combined range)
        combined_low = min(left.low_price, right.low_price)
        combined_high = max(left.high_price, right.high_price)
        combined_range = combined_high - combined_low
        buffer = combined_range * Decimal("0.10")
        price_overlap = (
            right.low_price <= left.high_price + buffer and
            right.high_price >= left.low_price - buffer
        )

        return time_close_enough and price_overlap

    def _merge_zones(self, left: AccumulationZone, right: AccumulationZone) -> AccumulationZone:
        """Merge two compatible zones into one extended zone."""
        return AccumulationZone(
            start_time=min(left.start_time, right.start_time),
            end_time=max(left.end_time, right.end_time),
            high_price=max(left.high_price, right.high_price),
            low_price=min(left.low_price, right.low_price),
            candle_count=left.candle_count + right.candle_count,
            strength=max(left.strength, right.strength),
            zone_type=ZoneType.ACCUMULATION,
        )

    def _merge_overlapping_zones(
        self, zones: list[AccumulationZone]
    ) -> list[AccumulationZone]:
        """
        Merge zones that overlap or sit very close in time/price.
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

            if self._zones_can_merge(last, zone):
                merged[-1] = self._merge_zones(last, zone)
                continue

            merged.append(zone)

        return merged
