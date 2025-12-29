"""
Base indicator interface.

Defines the abstract base class that all indicators must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, Sequence, TypeVar

from domain.entities.candle import Candle

T = TypeVar("T")


class Indicator(ABC, Generic[T]):
    """
    Abstract base class for all trading indicators.

    Indicators analyze market data (candles) and produce signals
    or analysis results of type T.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the indicator name."""
        ...

    @abstractmethod
    def analyze(self, candles: Sequence[Candle]) -> T:
        """
        Analyze the given candles and return a result.

        Args:
            candles: Sequence of OHLCV candles to analyze.

        Returns:
            Analysis result of type T specific to the indicator.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset the indicator's internal state."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"

