from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from domain.entities.candle import Candle
from domain.exceptions.errors import DataProviderError
from domain.services.market_data_service import MarketDataService
from domain.value_objects.timeframe import Timeframe


class SimpleResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        import json

        return json.loads(self.text)


class UrlLibSession:
    """Lightweight HTTP client using the standard library."""

    def get(self, url: str, params: Dict[str, Any] | None = None, timeout: int | None = None) -> SimpleResponse:
        query = urlencode(params or {})
        full_url = f"{url}?{query}" if query else url
        request = Request(full_url)
        try:
            with urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8")
                status = response.getcode()
                return SimpleResponse(status_code=status, text=text)
        except HTTPError as exc:
            text = exc.read().decode("utf-8")
            return SimpleResponse(status_code=exc.code, text=text)
        except URLError as exc:  # pragma: no cover - network layer unlikely in tests
            raise DataProviderError(f"Network error contacting Twelve Data: {exc.reason}") from exc


class TwelveDataClient(MarketDataService):
    """Data provider that integrates with the Twelve Data API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.twelvedata.com",
        session: UrlLibSession | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Twelve Data API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or UrlLibSession()

    def get_latest_ohlcv(
        self, symbol: str, timeframe: Timeframe, count: int = 1
    ) -> Sequence[Candle]:
        values = self._fetch_time_series(
            symbol=symbol, timeframe=timeframe, params={"outputsize": count}
        )
        return [self._build_candle(symbol, timeframe, entry) for entry in values]

    def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[Candle]:
        params: Dict[str, Any] = {}
        if start:
            params["start_date"] = start.isoformat()
        if end:
            params["end_date"] = end.isoformat()
        if limit:
            params["outputsize"] = limit

        values = self._fetch_time_series(symbol=symbol, timeframe=timeframe, params=params)
        return [self._build_candle(symbol, timeframe, entry) for entry in values]

    def _fetch_time_series(
        self, symbol: str, timeframe: Timeframe, params: Dict[str, Any]
    ) -> list[Dict[str, Any]]:
        merged_params = {
            "symbol": symbol,
            "interval": timeframe.to_twelvedata_interval(),
            "apikey": self.api_key,
            "format": "JSON",
            "dp": 8,
            "timezone": "UTC",
        }
        merged_params.update(params)

        response = self.session.get(f"{self.base_url}/time_series", params=merged_params, timeout=10)
        if response.status_code != 200:
            raise DataProviderError(
                f"Twelve Data returned HTTP {response.status_code}: {response.text}"
            )

        payload = response.json()
        if "status" in payload and payload.get("status") == "error":
            raise DataProviderError(payload.get("message", "Unknown Twelve Data error"))

        values = payload.get("values")
        if not isinstance(values, list):
            raise DataProviderError("Unexpected Twelve Data payload; missing 'values'")

        return values

    def _build_candle(
        self, symbol: str, timeframe: Timeframe, entry: Dict[str, Any]
    ) -> Candle:
        try:
            timestamp = datetime.fromisoformat(entry["datetime"])
            open_price = Decimal(entry["open"])
            high = Decimal(entry["high"])
            low = Decimal(entry["low"])
            close = Decimal(entry["close"])
            volume = Decimal(entry.get("volume", "0"))
        except (KeyError, ValueError, TypeError) as exc:
            raise DataProviderError(f"Invalid candle entry from Twelve Data: {entry}") from exc

        return Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
