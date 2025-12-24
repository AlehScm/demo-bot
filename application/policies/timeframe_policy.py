from __future__ import annotations

from domain.exceptions.errors import UnsupportedTimeframeError
from domain.value_objects.timeframe import Timeframe


class TimeframePolicy:
    """Validates whether a timeframe is supported by the application."""

    def __init__(self, allowed_timeframes: list[Timeframe] | None = None) -> None:
        self.allowed_timeframes = allowed_timeframes or list(Timeframe)

    def ensure_supported(self, timeframe: Timeframe) -> Timeframe:
        if timeframe not in self.allowed_timeframes:
            raise UnsupportedTimeframeError(f"Timeframe {timeframe} is not supported")
        return timeframe
