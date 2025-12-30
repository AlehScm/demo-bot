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
    seed_candles: int = 50
    break_invalid_pct: Decimal = Decimal("0.2")
    break_confirm_candles: int = 2

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
        if self.seed_candles <= 0:
            raise ValueError("seed_candles must be greater than zero.")
        if not 0 < self.break_invalid_pct <= 1:
            raise ValueError("break_invalid_pct must be between 0 and 1.")
        if self.break_confirm_candles <= 0:
            raise ValueError("break_confirm_candles must be greater than zero.")
