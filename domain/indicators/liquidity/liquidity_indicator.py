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
    LiquidityEventDirection,
    LiquiditySweep,
    LiquiditySignal,
    RangeBreak,
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

        # Use reasonable step to scan without skipping adjacent consolidations
        step = max(min_window // 3, 5)
        window_increment = max(min_window // 2, 3)

        for window_size in range(min_window, max_window + 1, window_increment):
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

        if range_size <= 0:
            return None

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

        # Reject if net drift is too large relative to range (impulsive move)
        if self._net_drift_too_high(window, high_price, low_price):
            return None

        # Reject if linear slope of closes indicates meaningful trend
        if self._slope_too_strong(window):
            return None

        # Count boundary touches (support/resistance tests)
        touches = self._count_boundary_touches(window, high_price, low_price)
        if touches < self._settings.min_boundary_touches:
            return None

        # Calculate strength
        strength = self._calculate_zone_strength(window, range_percent, touches)

        sweeps, range_break = self._detect_liquidity_events(
            window=window,
            high_price=high_price,
            low_price=low_price,
        )

        return AccumulationZone(
            start_time=window[0].timestamp,
            end_time=window[-1].timestamp,
            high_price=high_price,
            low_price=low_price,
            candle_count=len(window),
            strength=strength,
            zone_type=ZoneType.ACCUMULATION,
            liquidity_sweeps=sweeps,
            range_break=range_break,
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

    def _net_drift_too_high(
        self,
        window: Sequence[Candle],
        high: Decimal,
        low: Decimal,
    ) -> bool:
        """
        Reject windows where the end-to-start drift is too large vs range.

        Impulsive moves that trend should not be classified as sideways accumulation.
        """
        range_size = high - low
        if range_size <= 0:
            return True

        start_close = window[0].close
        end_close = window[-1].close
        drift = abs(end_close - start_close)
        drift_ratio = float(drift / range_size)

        return drift_ratio > self._settings.max_trend_drift_ratio

    def _slope_too_strong(self, window: Sequence[Candle]) -> bool:
        """
        Use simple linear regression slope of closes vs index to filter trends.

        The slope is normalized by average price and expressed in percent across
        the full window. Trending legs get rejected.
        """
        n = len(window)
        if n < 3:
            return True

        avg_price = sum(c.close for c in window) / n
        if avg_price == 0:
            return True

        # Compute slope manually without numpy
        indices = list(range(n))
        mean_idx = sum(indices) / n
        mean_close = avg_price

        num = sum((i - mean_idx) * (float(c.close) - float(mean_close)) for i, c in zip(indices, window))
        den = sum((i - mean_idx) ** 2 for i in indices)
        if den == 0:
            return True

        slope = num / den  # price units per candle
        slope_percent = abs(slope * (n - 1) / float(avg_price)) * 100  # over window length

        return slope_percent > self._settings.max_slope_percent

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

    def _detect_liquidity_events(
        self,
        window: Sequence[Candle],
        high_price: Decimal,
        low_price: Decimal,
    ) -> tuple[list[LiquiditySweep], RangeBreak | None]:
        """Detect sweeps (quick rejection) and range breaks (invalidations).

        Sweep: quick poke outside and close back inside within sweep_max_duration.
        Range break: penetration >= break_invalid_pct with confirmed closes outside.
        """
        sweeps: list[LiquiditySweep] = []
        range_break: RangeBreak | None = None

        range_height = high_price - low_price
        if range_height <= 0:
            return sweeps, range_break

        sweep_window: list[Candle] = []
        currently_violation: LiquidityEventDirection | None = None

        def finalize_sweep(event_direction: LiquidityEventDirection, candles_span: list[Candle]) -> None:
            if not candles_span:
                return
            penetration = self._calculate_penetration_percent(candles_span, high_price, low_price, range_height)
            sweeps.append(
                LiquiditySweep(
                    start_time=candles_span[0].timestamp,
                    end_time=candles_span[-1].timestamp,
                    direction=event_direction,
                    penetration_percent=penetration,
                    candle_count=len(candles_span),
                )
            )

        for candle in window:
            above_high = candle.high > high_price
            below_low = candle.low < low_price

            if above_high and not below_low:
                direction = LiquidityEventDirection.ABOVE
            elif below_low and not above_high:
                direction = LiquidityEventDirection.BELOW
            else:
                direction = None

            if direction:
                # Start or continue a violation cluster
                if currently_violation is None:
                    sweep_window = [candle]
                    currently_violation = direction
                elif direction == currently_violation:
                    sweep_window.append(candle)
                else:
                    # Different side without resolving prior; treat previous as finished outside
                    sweep_window = [candle]
                    currently_violation = direction
                continue

            # No violation on this candle => we might close a sweep if price closed back inside
            if sweep_window:
                last_violation = sweep_window[-1]
                closes_back_inside = (
                    (currently_violation == LiquidityEventDirection.ABOVE and last_violation.close < high_price) or
                    (currently_violation == LiquidityEventDirection.BELOW and last_violation.close > low_price)
                )
                duration_ok = len(sweep_window) <= self._settings.sweep_max_duration

                if closes_back_inside and duration_ok:
                    finalize_sweep(currently_violation, sweep_window)
                else:
                    # Potential range break: evaluate penetration and closes outside
                    penetration = self._calculate_penetration_percent(
                        sweep_window, high_price, low_price, range_height
                    )
                    if penetration >= self._settings.break_invalid_pct:
                        closes_outside = self._count_closes_outside(
                            sweep_window, high_price, low_price, currently_violation
                        )
                        if closes_outside >= self._settings.break_confirm_candles:
                            range_break = RangeBreak(
                                start_time=sweep_window[0].timestamp,
                                end_time=sweep_window[-1].timestamp,
                                direction=currently_violation,
                                penetration_percent=penetration,
                                candle_count=len(sweep_window),
                                closes_outside=closes_outside,
                            )
                            break
                sweep_window = []
                currently_violation = None

        return sweeps, range_break

    def _calculate_penetration_percent(
        self,
        candles_span: Sequence[Candle],
        high_price: Decimal,
        low_price: Decimal,
        range_height: Decimal,
    ) -> float:
        max_high = max(c.high for c in candles_span)
        min_low = min(c.low for c in candles_span)
        above = max(Decimal(0), max_high - high_price)
        below = max(Decimal(0), low_price - min_low)
        penetration = max(above, below) / range_height
        return float(penetration)

    def _count_closes_outside(
        self,
        candles_span: Sequence[Candle],
        high_price: Decimal,
        low_price: Decimal,
        direction: LiquidityEventDirection,
    ) -> int:
        if direction == LiquidityEventDirection.ABOVE:
            return sum(1 for c in candles_span if c.close > high_price)
        return sum(1 for c in candles_span if c.close < low_price)

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
