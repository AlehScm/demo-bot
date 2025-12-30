from __future__ import annotations

from typing import Sequence

from application.use_cases.detect_liquidity_zones import DetectLiquidityZones
from domain.entities.candle import Candle
from domain.indicators.liquidity import LiquiditySignal


class LiquidityController:
    """Controller coordinating liquidity zone detection without refetching candles."""

    def __init__(self, detect_liquidity_zones: DetectLiquidityZones) -> None:
        self.detect_liquidity_zones = detect_liquidity_zones

    def analyze(self, candles: Sequence[Candle]) -> LiquiditySignal:
        """Analyze pre-fetched candles for accumulation zones."""
        return self.detect_liquidity_zones.execute(candles)
