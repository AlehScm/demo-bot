from __future__ import annotations

from typing import Sequence

from application.use_cases.generate_trading_decision import (
    GenerateTradingDecision,
    TradingDecision,
)
from domain.value_objects.timeframe import Timeframe


class TradingController:
    """Controller that coordinates trading decision use cases."""

    def __init__(self, generate_decision: GenerateTradingDecision) -> None:
        self.generate_decision = generate_decision

    def get_decisions(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> Sequence[TradingDecision]:
        """
        Get trading decisions for a symbol and timeframe.

        Args:
            symbol: The trading symbol
            timeframe: The timeframe for analysis

        Returns:
            Sequence of trading decisions
        """
        return self.generate_decision.execute(
            symbol=symbol,
            timeframe=timeframe,
        )

