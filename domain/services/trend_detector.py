from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

from domain.entities.candle import Candle
from domain.value_objects.trend import Swing, SwingType, TrendDirection, TrendResult


@dataclass
class SwingSettings:
    """Configuration for swing validation and storage."""

    max_swings: int = 12
    min_price_move: Decimal | None = None
    min_percent_move: Decimal = Decimal("0.005")

    def is_significant(self, last_price: Decimal | None, candidate_price: Decimal) -> bool:
        """Check if the move between swings meets the configured thresholds."""

        if last_price is None:
            return True

        price_change = abs(candidate_price - last_price)

        if self.min_price_move is not None and price_change < self.min_price_move:
            return False

        if last_price == 0:
            return True

        percent_move = price_change / last_price
        return percent_move >= self.min_percent_move


class TrendDetector:
    """
    Central module for swing extraction and trend classification.

    - Detects objective pivot swings (zigzag-like) from OHLCV data.
    - Maintains a rolling memory of recent swings.
    - Classifies trend as UP, DOWN, or UNDEFINED based on HH/HL and LL/LH sequences.
    - Filters out micro-breaks using configurable movement thresholds.
    """

    def __init__(self, settings: SwingSettings | None = None) -> None:
        self.settings = settings or SwingSettings()
        self._swings: deque[Swing] = deque(maxlen=self.settings.max_swings)

    @property
    def swings(self) -> list[Swing]:
        """Expose a copy of the current swing memory."""

        return list(self._swings)

    def analyze(self, candles: Sequence[Candle]) -> TrendResult:
        """Process candles to update swing memory and classify the trend."""

        anchor_price = candles[0].close if candles else None

        for swing in self._detect_swings(candles):
            self._register_swing(swing, anchor_price)

        trend = self._classify_trend()
        confidence = self._compute_confidence(trend)
        reason = self._build_reason(trend)

        return TrendResult(
            trend=trend,
            confidence=confidence,
            last_swings=self.swings,
            reason=reason,
        )

    def _detect_swings(self, candles: Sequence[Candle]) -> Iterable[Swing]:
        if len(candles) < 2:
            return []

        swings: list[Swing] = []
        anchor = candles[0]
        direction: SwingType | None = None
        extreme_price = anchor.close
        extreme_idx = 0

        for idx in range(1, len(candles)):
            candle = candles[idx]

            if direction is None:
                if self.settings.is_significant(extreme_price, candle.close):
                    if candle.close > extreme_price:
                        swings.append(
                            Swing(
                                index=extreme_idx,
                                price=anchor.low,
                                timestamp=anchor.timestamp,
                                type=SwingType.LOW,
                            )
                        )
                        direction = SwingType.HIGH
                        extreme_price = candle.high
                        extreme_idx = idx
                    elif candle.close < extreme_price:
                        swings.append(
                            Swing(
                                index=extreme_idx,
                                price=anchor.high,
                                timestamp=anchor.timestamp,
                                type=SwingType.HIGH,
                            )
                        )
                        direction = SwingType.LOW
                        extreme_price = candle.low
                        extreme_idx = idx
                continue

            if direction is SwingType.HIGH:
                if candle.high >= extreme_price:
                    extreme_price = candle.high
                    extreme_idx = idx
                    continue

                if self.settings.is_significant(extreme_price, candle.low):
                    swings.append(
                        Swing(
                            index=extreme_idx,
                            price=extreme_price,
                            timestamp=candles[extreme_idx].timestamp,
                            type=SwingType.HIGH,
                        )
                    )
                    direction = SwingType.LOW
                    extreme_price = candle.low
                    extreme_idx = idx
            else:
                if candle.low <= extreme_price:
                    extreme_price = candle.low
                    extreme_idx = idx
                    continue

                if self.settings.is_significant(extreme_price, candle.high):
                    swings.append(
                        Swing(
                            index=extreme_idx,
                            price=extreme_price,
                            timestamp=candles[extreme_idx].timestamp,
                            type=SwingType.LOW,
                        )
                    )
                    direction = SwingType.HIGH
                    extreme_price = candle.high
                    extreme_idx = idx

        if direction is not None:
            swings.append(
                Swing(
                    index=extreme_idx,
                    price=extreme_price,
                    timestamp=candles[extreme_idx].timestamp,
                    type=direction,
                )
            )

        return swings

    def _register_swing(self, swing: Swing, anchor_price: Decimal | None) -> None:
        last_swing = self._swings[-1] if self._swings else None
        baseline_price = last_swing.price if last_swing else anchor_price

        if not self.settings.is_significant(baseline_price, swing.price):
            return

        if last_swing and last_swing.type == swing.type:
            should_replace = False

            if swing.type is SwingType.HIGH and swing.price >= last_swing.price:
                should_replace = True
            elif swing.type is SwingType.LOW and swing.price <= last_swing.price:
                should_replace = True

            if should_replace:
                self._swings.pop()
                self._swings.append(swing)
            return

        self._swings.append(swing)

    def _classify_trend(self) -> TrendDirection:
        highs = [s for s in self._swings if s.type is SwingType.HIGH]
        lows = [s for s in self._swings if s.type is SwingType.LOW]

        if len(highs) >= 2 and len(lows) >= 2:
            last_highs = highs[-2:]
            last_lows = lows[-2:]

            if last_highs[-1].price > last_highs[0].price and last_lows[-1].price > last_lows[0].price:
                return TrendDirection.UP

            if last_highs[-1].price < last_highs[0].price and last_lows[-1].price < last_lows[0].price:
                return TrendDirection.DOWN

        if highs and lows:
            last_swing = self._swings[-1]

            if last_swing.type is SwingType.LOW:
                last_low = lows[-1]
                prior_low = lows[-2] if len(lows) >= 2 else None
                last_high = highs[-1]

                if prior_low and last_low.price < prior_low.price:
                    return TrendDirection.DOWN

                if self.settings.is_significant(last_high.price, last_low.price) and last_low.price < last_high.price:
                    return TrendDirection.DOWN

            if last_swing.type is SwingType.HIGH:
                last_high = highs[-1]
                prior_high = highs[-2] if len(highs) >= 2 else None
                last_low = lows[-1]

                if prior_high and last_high.price > prior_high.price:
                    return TrendDirection.UP

                if self.settings.is_significant(last_low.price, last_high.price) and last_high.price > last_low.price:
                    return TrendDirection.UP

        return TrendDirection.undefined()

    def _compute_confidence(self, trend: TrendDirection) -> float:
        if trend == TrendDirection.undefined():
            return 0.25 if self._swings else 0.0

        depth_factor = min(len(self._swings) / max(self.settings.max_swings, 1), 1)
        return float(min(1, 0.45 + 0.45 * depth_factor))

    def _build_reason(self, trend: TrendDirection) -> str:
        if trend is TrendDirection.UP:
            return "Higher high and higher low detected; upward trend in play."
        if trend is TrendDirection.DOWN:
            return "Lower high and lower low detected; downward trend in play."
        if not self._swings:
            return "No valid swings detected; trend undefined."
        return "Swing data present but lacks HH/HL or LH/LL confirmation."
