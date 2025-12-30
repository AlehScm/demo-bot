from __future__ import annotations

from typing import Sequence

from domain.entities.candle import Candle
from domain.indicators.liquidity import LiquidityIndicator, LiquidityIndicatorSettings, LiquiditySignal


class DetectLiquidityZones:
    """Use case for detecting accumulation zones using provided candles."""

    def __init__(self, liquidity_settings: LiquidityIndicatorSettings) -> None:
        self.liquidity_settings = liquidity_settings

    def execute(self, candles: Sequence[Candle]) -> LiquiditySignal:
        """Detect accumulation zones from candles (expects oldest → newest order)."""
        ordered = list(candles)
        if not ordered:
            return LiquiditySignal(
                accumulation_zones=[],
                total_zones=0,
                analysis_period_start=None,
                analysis_period_end=None,
            )

        if ordered[0].timestamp > ordered[-1].timestamp:
            ordered.reverse()

        indicator = LiquidityIndicator(settings=self.liquidity_settings)
        indicator.reset()
        return indicator.analyze(ordered)
