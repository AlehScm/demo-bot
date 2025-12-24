from __future__ import annotations

from domain.entities.candle import Candle


def format_candles(candles: list[Candle]) -> str:
    """Return a human readable string for a list of candles."""
    lines: list[str] = []
    for candle in candles:
        lines.append(
            f"{candle.symbol} {candle.timeframe.value} @ {candle.timestamp.isoformat()} "
            f"O:{candle.open} H:{candle.high} L:{candle.low} C:{candle.close} V:{candle.volume}"
        )
    return "\n".join(lines)
