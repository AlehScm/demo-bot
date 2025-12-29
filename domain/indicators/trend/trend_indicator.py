"""
Trend Indicator using Market Structure analysis.

Detects swing points (HH, HL, LL, LH) and Break of Structure (BOS)
to determine market trend direction based on SMC/ICT concepts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from domain.entities.candle import Candle
from domain.indicators.base import Indicator
from domain.indicators.trend.models import (
    BOSType,
    BreakOfStructure,
    SwingClassification,
    SwingPoint,
    TrendDirection,
    TrendSignal,
)


@dataclass
class TrendIndicatorSettings:
    """Configuration for the trend indicator."""

    max_swings: int = 20
    min_percent_move: Decimal = Decimal("0.003")  # 0.3% minimum move
    lookback_bars: int = 3  # Bars to confirm swing

    def is_significant_move(self, from_price: Decimal, to_price: Decimal) -> bool:
        """Check if the price move is significant enough."""
        if from_price == 0:
            return True
        percent_move = abs(to_price - from_price) / from_price
        return percent_move >= self.min_percent_move


class TrendIndicator(Indicator[TrendSignal]):
    """
    Trend indicator based on market structure analysis.

    Identifies:
    - Swing Highs and Swing Lows
    - Classifies swings as HH, HL, LL, LH
    - Detects Break of Structure (BOS) for trend continuation

    Based on SMC/ICT trading concepts.
    """

    def __init__(self, settings: TrendIndicatorSettings | None = None) -> None:
        self._settings = settings or TrendIndicatorSettings()
        self._swings: deque[SwingPoint] = deque(maxlen=self._settings.max_swings)
        self._last_bos: BreakOfStructure | None = None
        self._current_trend: TrendDirection = TrendDirection.UNDEFINED

    @property
    def name(self) -> str:
        return "TrendIndicator"

    @property
    def swings(self) -> list[SwingPoint]:
        """Get the current list of swing points."""
        return list(self._swings)

    @property
    def last_bos(self) -> BreakOfStructure | None:
        """Get the last detected BOS."""
        return self._last_bos

    def reset(self) -> None:
        """Reset the indicator state."""
        self._swings.clear()
        self._last_bos = None
        self._current_trend = TrendDirection.UNDEFINED

    def analyze(self, candles: Sequence[Candle]) -> TrendSignal:
        """
        Analyze candles to detect market structure and trend.

        Args:
            candles: Sequence of OHLCV candles to analyze.

        Returns:
            TrendSignal with detected trend, swings, and BOS.
        """
        if len(candles) < self._settings.lookback_bars * 2 + 1:
            return TrendSignal(
                trend=TrendDirection.UNDEFINED,
                swings=[],
                confidence=0.0,
                reason="Dados insuficientes para análise",
            )

        # Step 1: Detect raw swing points
        raw_swings = self._detect_swing_points(candles)

        # Step 2: Classify swings as HH, HL, LL, LH
        classified_swings = self._classify_swings(raw_swings, candles)

        # Step 3: Update internal swing memory
        for swing in classified_swings:
            self._register_swing(swing)

        # Step 4: Detect BOS
        self._detect_bos(candles)

        # Step 5: Determine trend
        trend = self._determine_trend()
        confidence = self._calculate_confidence()
        reason = self._build_reason(trend)

        return TrendSignal(
            trend=trend,
            swings=self.swings,
            last_bos=self._last_bos,
            confidence=confidence,
            reason=reason,
        )

    def _detect_swing_points(self, candles: Sequence[Candle]) -> list[tuple[int, Decimal, bool]]:
        """
        Detect swing highs and lows using lookback confirmation.

        Returns list of tuples: (index, price, is_high)
        """
        swings: list[tuple[int, Decimal, bool]] = []
        lookback = self._settings.lookback_bars

        for i in range(lookback, len(candles) - lookback):
            candle = candles[i]

            # Check for swing high
            is_swing_high = all(
                candle.high >= candles[i - j].high and candle.high >= candles[i + j].high
                for j in range(1, lookback + 1)
            )

            # Check for swing low
            is_swing_low = all(
                candle.low <= candles[i - j].low and candle.low <= candles[i + j].low
                for j in range(1, lookback + 1)
            )

            if is_swing_high:
                swings.append((i, candle.high, True))

            if is_swing_low:
                swings.append((i, candle.low, False))

        return swings

    def _classify_swings(
        self, raw_swings: list[tuple[int, Decimal, bool]], candles: Sequence[Candle]
    ) -> list[SwingPoint]:
        """
        Classify swing points as HH, HL, LL, LH based on previous swings.
        """
        if not raw_swings:
            return []

        classified: list[SwingPoint] = []
        last_high: SwingPoint | None = None
        last_low: SwingPoint | None = None

        # Get last known highs and lows from memory
        for swing in self._swings:
            if swing.is_high:
                last_high = swing
            else:
                last_low = swing

        for idx, price, is_high in raw_swings:
            timestamp = candles[idx].timestamp

            if is_high:
                # Classify swing high
                if last_high is None:
                    classification = SwingClassification.SWING_HIGH
                elif price > last_high.price:
                    classification = SwingClassification.HIGHER_HIGH
                else:
                    classification = SwingClassification.LOWER_HIGH

                swing = SwingPoint(
                    price=price,
                    timestamp=timestamp,
                    index=idx,
                    classification=classification,
                )
                classified.append(swing)
                last_high = swing
            else:
                # Classify swing low
                if last_low is None:
                    classification = SwingClassification.SWING_LOW
                elif price > last_low.price:
                    classification = SwingClassification.HIGHER_LOW
                else:
                    classification = SwingClassification.LOWER_LOW

                swing = SwingPoint(
                    price=price,
                    timestamp=timestamp,
                    index=idx,
                    classification=classification,
                )
                classified.append(swing)
                last_low = swing

        return classified

    def _register_swing(self, swing: SwingPoint) -> None:
        """Register a new swing point in memory."""
        # Check for duplicate at same index
        if self._swings and self._swings[-1].index == swing.index:
            # Replace if same type and better price
            last = self._swings[-1]
            if last.is_high == swing.is_high:
                if (swing.is_high and swing.price >= last.price) or \
                   (swing.is_low and swing.price <= last.price):
                    self._swings.pop()
                    self._swings.append(swing)
                return

        self._swings.append(swing)

    def _detect_bos(self, candles: Sequence[Candle]) -> None:
        """
        Detect Break of Structure.

        BOS Bullish: Price breaks above the last significant swing high
        BOS Bearish: Price breaks below the last significant swing low
        """
        if len(self._swings) < 2:
            return

        # Find the last swing high and low
        last_swing_high: SwingPoint | None = None
        last_swing_low: SwingPoint | None = None

        for swing in reversed(list(self._swings)):
            if swing.is_high and last_swing_high is None:
                last_swing_high = swing
            elif swing.is_low and last_swing_low is None:
                last_swing_low = swing

            if last_swing_high and last_swing_low:
                break

        if not candles:
            return

        current_candle = candles[-1]

        # Check for bullish BOS (price breaks above swing high)
        if last_swing_high and current_candle.close > last_swing_high.price:
            if self._settings.is_significant_move(last_swing_high.price, current_candle.close):
                self._last_bos = BreakOfStructure(
                    type=BOSType.BULLISH,
                    broken_swing=last_swing_high,
                    break_price=current_candle.close,
                    break_timestamp=current_candle.timestamp,
                    break_index=len(candles) - 1,
                )
                self._current_trend = TrendDirection.UP

        # Check for bearish BOS (price breaks below swing low)
        elif last_swing_low and current_candle.close < last_swing_low.price:
            if self._settings.is_significant_move(last_swing_low.price, current_candle.close):
                self._last_bos = BreakOfStructure(
                    type=BOSType.BEARISH,
                    broken_swing=last_swing_low,
                    break_price=current_candle.close,
                    break_timestamp=current_candle.timestamp,
                    break_index=len(candles) - 1,
                )
                self._current_trend = TrendDirection.DOWN

    def _determine_trend(self) -> TrendDirection:
        """
        Determine the current trend based on swing structure.

        UP trend: HH + HL sequence
        DOWN trend: LL + LH sequence
        """
        if len(self._swings) < 4:
            return self._current_trend if self._current_trend != TrendDirection.UNDEFINED else TrendDirection.UNDEFINED

        # Get recent swing classifications
        recent_swings = list(self._swings)[-6:]

        highs = [s for s in recent_swings if s.is_high]
        lows = [s for s in recent_swings if s.is_low]

        if len(highs) >= 2 and len(lows) >= 2:
            last_two_highs = highs[-2:]
            last_two_lows = lows[-2:]

            # Check for bullish structure: HH + HL
            has_hh = last_two_highs[-1].classification == SwingClassification.HIGHER_HIGH
            has_hl = last_two_lows[-1].classification == SwingClassification.HIGHER_LOW

            if has_hh and has_hl:
                return TrendDirection.UP

            # Check for bearish structure: LL + LH
            has_ll = last_two_lows[-1].classification == SwingClassification.LOWER_LOW
            has_lh = last_two_highs[-1].classification == SwingClassification.LOWER_HIGH

            if has_ll and has_lh:
                return TrendDirection.DOWN

        # Fall back to BOS-based trend
        if self._last_bos:
            return TrendDirection.UP if self._last_bos.is_bullish else TrendDirection.DOWN

        return self._current_trend

    def _calculate_confidence(self) -> float:
        """Calculate confidence level based on available data."""
        if not self._swings:
            return 0.0

        base_confidence = 0.3

        # More swings = higher confidence
        swing_factor = min(len(self._swings) / self._settings.max_swings, 1.0) * 0.3

        # BOS confirmation adds confidence
        bos_factor = 0.2 if self._last_bos else 0.0

        # Consistent structure adds confidence
        structure_factor = 0.0
        if len(self._swings) >= 4:
            recent = list(self._swings)[-4:]
            classifications = [s.classification for s in recent]

            # Check for consistent bullish or bearish structure
            bullish_count = sum(
                1 for c in classifications
                if c in (SwingClassification.HIGHER_HIGH, SwingClassification.HIGHER_LOW)
            )
            bearish_count = sum(
                1 for c in classifications
                if c in (SwingClassification.LOWER_LOW, SwingClassification.LOWER_HIGH)
            )

            if bullish_count >= 3 or bearish_count >= 3:
                structure_factor = 0.2

        return min(base_confidence + swing_factor + bos_factor + structure_factor, 1.0)

    def _build_reason(self, trend: TrendDirection) -> str:
        """Build a human-readable reason for the trend determination."""
        if not self._swings:
            return "Nenhum swing detectado ainda."

        if len(self._swings) < 4:
            return f"Apenas {len(self._swings)} swings detectados. Aguardando mais dados."

        reasons = []

        # Describe recent structure
        recent = list(self._swings)[-4:]
        structure_desc = " → ".join([s.classification.value for s in recent])
        reasons.append(f"Estrutura recente: {structure_desc}")

        # Describe BOS if present
        if self._last_bos:
            bos_type = "alta" if self._last_bos.is_bullish else "baixa"
            reasons.append(f"BOS de {bos_type} confirmado em {self._last_bos.break_price}")

        # Describe trend
        if trend == TrendDirection.UP:
            reasons.append("Tendência de ALTA: Higher Highs e Higher Lows detectados")
        elif trend == TrendDirection.DOWN:
            reasons.append("Tendência de BAIXA: Lower Lows e Lower Highs detectados")
        else:
            reasons.append("Tendência INDEFINIDA: Estrutura não clara")

        return ". ".join(reasons) + "."

