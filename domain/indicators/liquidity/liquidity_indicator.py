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
    # Tighter = more selective (4.5% tolerates realistic Wyckoff TRs)
    max_range_percent: Decimal = Decimal("4.5")

    # Minimum zone strength to report (0.0 to 1.0)
    min_strength: float = 0.5

    # Minimum touches on support/resistance to confirm accumulation
    min_boundary_touches: int = 2

    # Maximum zones to return (most significant ones)
    max_zones: int = 5

    # Minimum gap between zones (in candles) to avoid clustering
    min_gap_between_zones: int = 15

    # Volume spike required to qualify a Selling Climax compared to average volume
    sc_volume_spike_ratio: Decimal = Decimal("1.8")

    # Range expansion factor to qualify a Selling Climax compared to average range
    sc_range_spike_ratio: Decimal = Decimal("1.6")

    # Minimum downtrend magnitude (percent drop) before PS/SC
    min_downtrend_drop_percent: Decimal = Decimal("1.0")

    # Lookback candles to validate downtrend before PS/SC
    downtrend_lookback: int = 12

    # Maximum candles between SC and AR to keep the TR compact
    max_candles_sc_to_ar: int = 20

    # Minimum secondary tests after AR to accept absorption evidence
    min_secondary_tests: int = 1

    # Penetration depth below support (as ATR multiple) to classify a Spring
    spring_penetration_atr: Decimal = Decimal("0.35")

    # Volume must contract on ST compared to SC by this factor
    st_volume_contraction: Decimal = Decimal("0.7")


class LiquidityIndicator(Indicator[LiquiditySignal]):
    """
    Liquidity indicator based on Wyckoff accumulation concepts.

    The indicator now follows the event sequencing described by Wyckoff:
    - Valida uma tendência de baixa anterior (PS/SC não aparecem em topos)
    - Procura por Selling Climax (SC) com pico de volume e range ampliado
    - Identifica o Automatic Rally (AR) após o SC para formar o topo do TR
    - Conta Secondary Tests (ST) com contração de volume na base do TR
    - Detecta Spring/Shakout (quebra rápida do suporte e fechamento interno)
    Cada etapa reforça a evidência de absorção de oferta antes de um movimento
    direcional de alta.
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
        Detect accumulation zones using a Wyckoff-oriented sliding window.
        """
        zones: list[AccumulationZone] = []
        min_window = self._settings.min_candles_in_zone
        max_window = max(min_window, min(len(candles), min_window * 4))

        # Use larger step to avoid too many similar zones
        step = max(min_window // 3, 8)

        for window_size in range(min_window, max_window + 1, 10):
            for start_idx in range(0, len(candles) - window_size + 1, step):
                end_idx = start_idx + window_size
                zone = self._analyze_window(candles, start_idx, end_idx)
                if zone is not None:
                    zones.append(zone)

        return zones

    def _analyze_window(
        self, candles: Sequence[Candle], start_idx: int, end_idx: int
    ) -> AccumulationZone | None:
        """
        Analyze a window of candles to determine if it's an accumulation zone.
        """
        window = candles[start_idx:end_idx]
        if len(window) < self._settings.min_candles_in_zone:
            return None

        # Require clear downtrend before accumulation starts
        if not self._has_previous_downtrend(candles, start_idx):
            return None

        avg_range = self._average_range(window)
        avg_volume = self._average_volume(window)

        sc_idx = self._find_selling_climax(window, avg_range, avg_volume)
        if sc_idx is None:
            return None

        ps_idx = self._find_preliminary_support(window, sc_idx, avg_range)
        ar_idx = self._find_automatic_rally(window, sc_idx, avg_range, avg_volume)
        if ar_idx is None:
            return None

        support = window[sc_idx].low
        resistance = window[ar_idx].high
        if resistance <= support:
            return None

        # Confirm tight range relative to average price
        avg_price = sum(c.close for c in window) / len(window)
        if avg_price == 0:
            return None
        range_percent = ((resistance - support) / avg_price) * 100
        if range_percent > self._settings.max_range_percent:
            return None

        # Secondary tests on support with volume contraction
        secondary_tests, st_indexes = self._count_secondary_tests(
            window, ar_idx, support, window[sc_idx].volume
        )
        if secondary_tests < self._settings.min_secondary_tests:
            return None

        # Springs after STs improve conviction but are optional
        spring_idx = self._find_spring(
            window,
            support,
            avg_range,
            window[sc_idx].volume,
            min(st_indexes) if st_indexes else ar_idx,
        )
        # Keep the trading range anchored at the SC low; springs are recorded
        # as event confirmations but do not overly stretch the box.
        zone_low = support

        # Boundary touches (resistance/support)
        touches = self._count_boundary_touches(window, resistance, zone_low)
        if touches < self._settings.min_boundary_touches:
            return None

        strength = self._calculate_zone_strength(
            window=window,
            high_price=resistance,
            low_price=zone_low,
            range_percent=range_percent,
            touches=touches,
            sc_idx=sc_idx,
            ar_idx=ar_idx,
            st_count=secondary_tests,
            spring_idx=spring_idx,
            avg_volume=avg_volume,
        )

        return AccumulationZone(
            start_time=window[ps_idx].timestamp if ps_idx is not None else window[sc_idx].timestamp,
            end_time=window[spring_idx].timestamp if spring_idx is not None else window[-1].timestamp,
            high_price=resistance,
            low_price=zone_low,
            candle_count=len(window),
            strength=strength,
            zone_type=ZoneType.ACCUMULATION,
        )

    def _has_previous_downtrend(self, candles: Sequence[Candle], start_idx: int) -> bool:
        """
        Validate that a meaningful downtrend precedes the accumulation window.

        Compares the close at the beginning of the lookback with the close at the
        window start and checks for consistent lower highs/lows.
        """
        lookback = self._settings.downtrend_lookback
        if start_idx < lookback:
            segment = candles[:lookback]
        else:
            segment = candles[start_idx - lookback:start_idx]
        if len(segment) < lookback:
            return False

        start_close = segment[0].close
        end_close = segment[-1].close
        if start_close == 0:
            return False

        drop_percent = ((start_close - end_close) / start_close) * 100
        if drop_percent < self._settings.min_downtrend_drop_percent:
            return False

        lower_highs = sum(
            1 for i in range(1, len(segment))
            if segment[i].high < segment[i - 1].high
        )
        lower_lows = sum(
            1 for i in range(1, len(segment))
            if segment[i].low < segment[i - 1].low
        )

        # Require majority of candles to print lower highs and lows
        return (
            lower_highs >= lookback * 0.6 and
            lower_lows >= lookback * 0.6
        )

    def _find_selling_climax(
        self,
        window: Sequence[Candle],
        avg_range: Decimal,
        avg_volume: Decimal,
    ) -> int | None:
        """
        Find Selling Climax (SC) characterized by volume spike and expanded range.
        """
        sc_idx = None
        best_score = Decimal("0")
        for idx, candle in enumerate(window):
            range_size = candle.high - candle.low
            if avg_range == 0 or avg_volume == 0:
                continue

            volume_ratio = candle.volume / avg_volume
            range_ratio = range_size / avg_range

            if (
                volume_ratio >= self._settings.sc_volume_spike_ratio and
                range_ratio >= self._settings.sc_range_spike_ratio and
                candle.close <= candle.open  # climax to downside
            ):
                score = volume_ratio + range_ratio
                if sc_idx is None or score > best_score:
                    sc_idx = idx
                    best_score = score
        return sc_idx

    def _find_preliminary_support(
        self,
        window: Sequence[Candle],
        sc_idx: int,
        avg_range: Decimal,
    ) -> int | None:
        """
        Identify Preliminary Support (PS) prior to SC as a local low with
        slowing momentum.
        """
        if sc_idx == 0:
            return None

        ps_window = window[max(0, sc_idx - 5):sc_idx]
        ps_idx = None
        best_distance = Decimal("0")
        for idx, candle in enumerate(ps_window):
            distance = abs(candle.low - window[sc_idx].low)
            range_size = candle.high - candle.low
            if range_size <= avg_range * Decimal("1.05"):
                if ps_idx is None or distance > best_distance:
                    ps_idx = max(0, sc_idx - 5) + idx
                    best_distance = distance
        return ps_idx

    def _find_automatic_rally(
        self,
        window: Sequence[Candle],
        sc_idx: int,
        avg_range: Decimal,
        avg_volume: Decimal,
    ) -> int | None:
        """
        Find Automatic Rally (AR) after SC: strong upward reaction defining TR top.
        """
        lookahead = min(self._settings.max_candles_sc_to_ar, len(window) - sc_idx - 1)
        if lookahead <= 0:
            return None

        ar_slice = window[sc_idx + 1: sc_idx + 1 + lookahead]
        ar_idx = None
        best_height = Decimal("-1")
        for idx, candle in enumerate(ar_slice, start=sc_idx + 1):
            range_size = candle.high - candle.low
            range_ok = range_size >= avg_range * Decimal("0.8")
            volume_ok = avg_volume == 0 or candle.volume >= avg_volume * Decimal("0.8")
            closes_up = candle.close > candle.open
            distance_from_sc = candle.high - window[sc_idx].low

            if range_ok and volume_ok and closes_up and distance_from_sc > best_height:
                ar_idx = idx
                best_height = distance_from_sc
        return ar_idx

    def _count_secondary_tests(
        self,
        window: Sequence[Candle],
        ar_idx: int,
        support: Decimal,
        sc_volume: Decimal,
    ) -> tuple[int, list[int]]:
        """
        Count Secondary Tests (ST) retesting support with contracting volume.
        """
        st_indexes: list[int] = []
        tolerance = (max(c.high for c in window) - min(c.low for c in window)) * Decimal("0.35")
        for idx, candle in enumerate(window[ar_idx + 1:], start=ar_idx + 1):
            near_support = candle.low <= support + tolerance
            volume_contracts = (
                sc_volume == 0 or candle.volume <= sc_volume * self._settings.st_volume_contraction
            )
            narrow_body = (candle.high - candle.low) <= (max(Decimal("0.0001"), tolerance))

            if near_support and volume_contracts and narrow_body:
                st_indexes.append(idx)

        return len(st_indexes), st_indexes

    def _find_spring(
        self,
        window: Sequence[Candle],
        support: Decimal,
        avg_range: Decimal,
        sc_volume: Decimal,
        from_idx: int,
    ) -> int | None:
        """
        Detect Spring/Shakout: penetration below support with fast recovery.
        """
        penetration = avg_range * self._settings.spring_penetration_atr
        if penetration <= 0:
            return None

        for idx, candle in enumerate(window[from_idx:], start=from_idx):
            breaks_support = candle.low < support - penetration
            closes_above = candle.close > support
            volume_ok = sc_volume == 0 or candle.volume <= sc_volume * Decimal("1.3")

            if breaks_support and closes_above and volume_ok:
                return idx
        return None

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
        self,
        window: Sequence[Candle],
        high_price: Decimal,
        low_price: Decimal,
        range_percent: Decimal,
        touches: int,
        sc_idx: int,
        ar_idx: int,
        st_count: int,
        spring_idx: int | None,
        avg_volume: Decimal,
    ) -> float:
        """
        Calculate the strength of an accumulation zone.

        Strength is based on:
        - Tighter range = stronger (max contribution: 0.25)
        - More candles = stronger (max contribution: 0.18)
        - More boundary touches = stronger (max contribution: 0.2)
        - Price concentration near middle = stronger (max contribution: 0.15)
        - Wyckoff structure confirmations (SC->AR->STs->Spring) (max: 0.3)
        """
        # Range tightness factor (tighter = better)
        max_range = float(self._settings.max_range_percent)
        range_factor = 1.0 - min(float(range_percent) / max_range, 1.0)
        range_contribution = range_factor * 0.25

        # Candle count factor
        min_candles = self._settings.min_candles_in_zone
        max_bonus_candles = min_candles * 3
        candle_factor = min(
            (len(window) - min_candles) / (max_bonus_candles - min_candles),
            1.0
        )
        candle_contribution = max(0, candle_factor) * 0.18

        # Boundary touches factor
        min_touches = self._settings.min_boundary_touches
        max_touches = min_touches * 3
        touch_factor = min((touches - min_touches) / (max_touches - min_touches), 1.0)
        touch_contribution = max(0, touch_factor) * 0.2

        # Price concentration factor (how much price stays near middle)
        mid_price = (high_price + low_price) / 2
        deviations = [
            abs(c.close - mid_price) / mid_price if mid_price > 0 else Decimal(0)
            for c in window
        ]
        avg_deviation = sum(deviations) / len(deviations) if deviations else Decimal(0)
        concentration_factor = 1.0 - min(float(avg_deviation) * 20, 1.0)
        concentration_contribution = max(0, concentration_factor) * 0.15

        # Structural confirmation factor
        structure_score = 0.0
        sc_volume = window[sc_idx].volume
        if avg_volume > 0:
            sc_volume_factor = min(float(sc_volume / avg_volume) / 3.0, 1.0)
            structure_score += sc_volume_factor * 0.15

        # Presence of multiple STs adds conviction
        st_factor = min(st_count / 3, 1.0)
        structure_score += st_factor * 0.1

        if spring_idx is not None:
            structure_score += 0.05

        structure_contribution = min(structure_score, 0.3)

        return min(
            range_contribution
            + candle_contribution
            + touch_contribution
            + concentration_contribution
            + structure_contribution,
            1.0
        )

    def _average_range(self, window: Sequence[Candle]) -> Decimal:
        """Average true range proxy using high-low spread."""
        if not window:
            return Decimal(0)
        return sum((c.high - c.low) for c in window) / len(window)

    def _average_volume(self, window: Sequence[Candle]) -> Decimal:
        """Average volume for a sequence of candles."""
        if not window:
            return Decimal(0)
        return sum(c.volume for c in window) / len(window)

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
