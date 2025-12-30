from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from application.use_cases.detect_liquidity_zones import DetectLiquidityZones
from domain.entities.candle import Candle
from domain.indicators.liquidity import LiquidityIndicatorSettings
from domain.value_objects.timeframe import Timeframe


def test_detect_liquidity_zones_does_not_reorder_when_chronological():
    settings = LiquidityIndicatorSettings(
        min_candles_in_zone=2,
        max_range_percent=Decimal("5"),
        min_strength=0.1,
        min_boundary_touches=1,
        max_zones=1,
        min_gap_between_zones=0,
    )
    use_case = DetectLiquidityZones(liquidity_settings=settings)

    now = datetime.utcnow()
    candles = [
        Candle(
            symbol="TEST",
            timeframe=Timeframe.ONE_MINUTE,
            timestamp=now - timedelta(minutes=1),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        ),
        Candle(
            symbol="TEST",
            timeframe=Timeframe.ONE_MINUTE,
            timestamp=now,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100.5"),
            volume=Decimal("12"),
        ),
    ]

    signal = use_case.execute(candles)

    assert signal.analysis_period_start == candles[0].timestamp
    assert signal.analysis_period_end == candles[-1].timestamp
