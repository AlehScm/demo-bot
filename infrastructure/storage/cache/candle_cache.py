from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from domain.entities.candle import Candle
from domain.value_objects.timeframe import Timeframe


class CandleCache:
    """File-based cache to reuse fetched candles across controllers."""

    def __init__(self, cache_file: str | Path) -> None:
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.cache_file.exists():
            self.cache_file.write_text("{}")

    def get(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle] | None:
        cache = self._read_cache()
        key = self._build_key(symbol, timeframe, count)
        entry = cache.get(key)
        if not entry:
            return None

        try:
            return [self._deserialize_candle(item) for item in entry["candles"]]
        except (KeyError, ValueError):
            return None

    def set(self, symbol: str, timeframe: Timeframe, count: int, candles: list[Candle]) -> None:
        cache = self._read_cache()
        key = self._build_key(symbol, timeframe, count)
        cache[key] = {
            "stored_at": datetime.utcnow().isoformat(),
            "candles": [self._serialize_candle(c) for c in candles],
        }
        self._write_cache(cache)

    def _read_cache(self) -> dict[str, Any]:
        if not self.cache_file.exists():
            return {}
        try:
            return json.loads(self.cache_file.read_text())
        except json.JSONDecodeError:
            return {}

    def _write_cache(self, data: dict[str, Any]) -> None:
        self.cache_file.write_text(json.dumps(data))

    @staticmethod
    def _build_key(symbol: str, timeframe: Timeframe, count: int) -> str:
        return f"{symbol}_{timeframe.value}_{count}"

    @staticmethod
    def _serialize_candle(candle: Candle) -> dict[str, Any]:
        return {
            "symbol": candle.symbol,
            "timeframe": candle.timeframe.value,
            "timestamp": candle.timestamp.isoformat(),
            "open": str(candle.open),
            "high": str(candle.high),
            "low": str(candle.low),
            "close": str(candle.close),
            "volume": str(candle.volume),
        }

    @staticmethod
    def _deserialize_candle(data: dict[str, Any]) -> Candle:
        return Candle(
            symbol=data["symbol"],
            timeframe=Timeframe(data["timeframe"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open=Decimal(data["open"]),
            high=Decimal(data["high"]),
            low=Decimal(data["low"]),
            close=Decimal(data["close"]),
            volume=Decimal(data["volume"]),
        )
