from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from application.use_cases.fetch_latest_ohlcv import FetchLatestOHLCV
from domain.entities.candle import Candle
from domain.services.trend_detector import TrendDetector
from domain.value_objects.timeframe import Timeframe
from domain.value_objects.trend import TrendDirection


@dataclass
class TradingDecision:
    """Represents a trading decision made by the bot."""

    time: int  # Unix timestamp in seconds
    type: str  # 'buy' or 'sell'
    price: float
    text: str


class GenerateTradingDecision:
    """Use case to generate trading decisions based on trend analysis."""

    def __init__(
        self,
        fetch_latest: FetchLatestOHLCV,
        trend_detector: TrendDetector,
    ) -> None:
        self.fetch_latest = fetch_latest
        self.trend_detector = trend_detector

    def execute(
        self,
        symbol: str,
        timeframe: Timeframe,
        analysis_candles_count: int = 5000,
    ) -> Sequence[TradingDecision]:
        """
        Generate trading decisions based on trend analysis.

        Args:
            symbol: The trading symbol to analyze
            timeframe: The timeframe for the candles
            analysis_candles_count: Number of candles to use for analysis

        Returns:
            Sequence of trading decisions
        """
        # Fetch candles for analysis
        candles = self.fetch_latest.execute(
            symbol=symbol,
            timeframe=timeframe,
            count=analysis_candles_count,
        )
        candles_list = list(candles)

        if not candles_list:
            return []

        # Analyze trend
        trend_result = self.trend_detector.analyze(candles_list)

        # Get last candle for current price and timestamp
        last_candle = candles_list[-1]
        current_price = float(last_candle.close)
        last_candle_time = int(last_candle.timestamp.timestamp())

        decisions: list[TradingDecision] = []

        # Strategy 1: Use trend analysis if confidence is sufficient
        if trend_result.confidence > 0.3:
            if trend_result.trend == TrendDirection.UP:
                decisions.append(
                    TradingDecision(
                        time=last_candle_time,
                        type="buy",
                        price=current_price,
                        text=f"Tendência de alta (conf: {trend_result.confidence:.2f})",
                    )
                )
            elif trend_result.trend == TrendDirection.DOWN:
                decisions.append(
                    TradingDecision(
                        time=last_candle_time,
                        type="sell",
                        price=current_price,
                        text=f"Tendência de queda (conf: {trend_result.confidence:.2f})",
                    )
                )
        else:
            # Strategy 2: Fallback to simple momentum analysis
            decisions.extend(
                self._analyze_momentum(candles_list, last_candle_time, current_price)
            )

        return decisions

    def _analyze_momentum(
        self, candles_list: list[Candle], timestamp: int, current_price: float
    ) -> list[TradingDecision]:
        """
        Analyze price momentum using simple moving average comparison.

        Args:
            candles_list: List of candles to analyze
            timestamp: Timestamp for the decision
            current_price: Current price

        Returns:
            List of trading decisions based on momentum
        """
        decisions: list[TradingDecision] = []

        if len(candles_list) >= 20:
            recent_prices = [float(c.close) for c in candles_list[-10:]]
            previous_prices = [float(c.close) for c in candles_list[-20:-10]]
            recent_avg = sum(recent_prices) / len(recent_prices)
            previous_avg = sum(previous_prices) / len(previous_prices)

            # If recent price is above previous average, positive momentum
            if recent_avg > previous_avg * 1.001:  # 0.1% difference
                percent_change = ((recent_avg / previous_avg - 1) * 100)
                decisions.append(
                    TradingDecision(
                        time=timestamp,
                        type="buy",
                        price=current_price,
                        text=f"Momentum positivo (+{percent_change:.2f}%)",
                    )
                )
            elif recent_avg < previous_avg * 0.999:  # 0.1% difference
                percent_change = ((recent_avg / previous_avg - 1) * 100)
                decisions.append(
                    TradingDecision(
                        time=timestamp,
                        type="sell",
                        price=current_price,
                        text=f"Momentum negativo ({percent_change:.2f}%)",
                    )
                )

        return decisions

