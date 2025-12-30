from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LiquidityIndicatorSettings:
    """Configuration for the liquidity indicator."""

    min_candles_in_zone: int = 25
    max_range_percent: Decimal = Decimal("0.8")
    min_strength: float = 0.55
    min_boundary_touches: int = 3
    max_zones: int = 5
    min_gap_between_zones: int = 15
    break_invalid_pct: float = 0.2  # penetration % of range height that invalidates the zone
    break_confirm_candles: int = 2  # closes outside to confirm break
    sweep_max_duration: int = 5  # max candles for a sweep (quick in/out)
    max_trend_drift_ratio: float = 0.6  # max net drift vs range height to still count as sideways
    max_slope_percent: float = 1.0  # max linear slope (close trend) in % of avg price across the window

    def __post_init__(self) -> None:
        if self.min_candles_in_zone <= 0:
            raise ValueError("min_candles_in_zone must be greater than zero.")
        if self.max_range_percent <= 0:
            raise ValueError("max_range_percent must be greater than zero.")
        if not 0.0 < self.min_strength <= 1.0:
            raise ValueError("min_strength must be between 0 and 1.")
        if self.min_boundary_touches <= 0:
            raise ValueError("min_boundary_touches must be greater than zero.")
        if self.max_zones <= 0:
            raise ValueError("max_zones must be greater than zero.")
        if self.min_gap_between_zones < 0:
            raise ValueError("min_gap_between_zones cannot be negative.")
        if not 0.0 < self.break_invalid_pct < 1.0:
            raise ValueError("break_invalid_pct must be between 0 and 1 (exclusive).")
        if self.break_confirm_candles <= 0:
            raise ValueError("break_confirm_candles must be greater than zero.")
        if self.sweep_max_duration <= 0:
            raise ValueError("sweep_max_duration must be greater than zero.")
        if not 0.0 < self.max_trend_drift_ratio < 2.0:
            raise ValueError("max_trend_drift_ratio must be between 0 and 2 (exclusive).")
        if not 0.0 < self.max_slope_percent < 5.0:
            raise ValueError("max_slope_percent must be between 0 and 5 (exclusive).")
