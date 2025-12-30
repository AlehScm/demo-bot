from __future__ import annotations

import os
from decimal import Decimal

from domain.indicators.liquidity import LiquidityIndicatorSettings


def _int_from_env(var_name: str, default: int) -> int:
    value = os.getenv(var_name)
    if value is None:
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{var_name} must be greater than zero.")
    return parsed


def _decimal_from_env(var_name: str, default: Decimal) -> Decimal:
    value = os.getenv(var_name)
    if value is None:
        return default
    parsed = Decimal(value)
    if parsed <= 0:
        raise ValueError(f"{var_name} must be greater than zero.")
    return parsed


def _float_from_env(var_name: str, default: float) -> float:
    value = os.getenv(var_name)
    if value is None:
        return default
    parsed = float(value)
    if not 0.0 < parsed <= 1.0:
        raise ValueError(f"{var_name} must be between 0 and 1.")
    return parsed


def load_liquidity_settings() -> LiquidityIndicatorSettings:
    """Load liquidity (accumulation) indicator settings from environment variables."""
    return LiquidityIndicatorSettings(
        min_candles_in_zone=_int_from_env("ACCUMULATION_MIN_CANDLES", 25),
        max_range_percent=_decimal_from_env("ACCUMULATION_MAX_RANGE_PERCENT", Decimal("0.8")),
        min_strength=_float_from_env("ACCUMULATION_MIN_STRENGTH", 0.55),
        min_boundary_touches=_int_from_env("ACCUMULATION_MIN_BOUNDARY_TOUCHES", 3),
        max_zones=_int_from_env("ACCUMULATION_MAX_ZONES", 5),
        min_gap_between_zones=_int_from_env("ACCUMULATION_MIN_GAP_BETWEEN_ZONES", 15),
        break_invalid_pct=float(os.getenv("ACCUMULATION_BREAK_INVALID_PCT", 0.2)),
        break_confirm_candles=_int_from_env("ACCUMULATION_BREAK_CONFIRM_CANDLES", 2),
        sweep_max_duration=_int_from_env("ACCUMULATION_SWEEP_MAX_DURATION", 5),
        max_trend_drift_ratio=float(os.getenv("ACCUMULATION_MAX_TREND_DRIFT_RATIO", 0.6)),
        max_slope_percent=float(os.getenv("ACCUMULATION_MAX_SLOPE_PERCENT", 1.0)),
    )
