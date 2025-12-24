from datetime import datetime
from decimal import Decimal

import pytest

from domain.exceptions.errors import DataProviderError
from domain.value_objects.timeframe import Timeframe
from infrastructure.data_providers.twelve_data_client import TwelveDataClient


class MockResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = "mock response"

    def json(self) -> dict:
        return self._payload


class MockSession:
    def __init__(self, response: MockResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def get(self, url: str, params: dict | None = None, timeout: int | None = None) -> MockResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.response


def test_get_latest_ohlcv_returns_candles() -> None:
    payload = {
        "values": [
            {
                "datetime": "2024-01-01 00:00:00",
                "open": "100.0",
                "high": "110.0",
                "low": "90.0",
                "close": "105.0",
                "volume": "1500",
            },
            {
                "datetime": "2023-12-31 23:59:00",
                "open": "95.0",
                "high": "100.0",
                "low": "90.0",
                "close": "98.0",
                "volume": "1200",
            },
        ]
    }
    session = MockSession(MockResponse(payload))
    client = TwelveDataClient(api_key="fake", session=session, base_url="http://mock")

    candles = client.get_latest_ohlcv("AAPL", Timeframe.ONE_MINUTE, count=2)

    assert len(candles) == 2
    assert candles[0].open == Decimal("100.0")
    assert candles[0].timestamp == datetime.fromisoformat("2024-01-01 00:00:00")
    assert session.calls[0]["params"]["interval"] == "1min"
    assert session.calls[0]["params"]["outputsize"] == 2


def test_get_historical_ohlcv_applies_date_filters() -> None:
    payload = {
        "values": [
            {
                "datetime": "2024-01-01 00:00:00",
                "open": "100.0",
                "high": "110.0",
                "low": "90.0",
                "close": "105.0",
                "volume": "1500",
            }
        ]
    }
    session = MockSession(MockResponse(payload))
    client = TwelveDataClient(api_key="fake", session=session, base_url="http://mock")

    start = datetime(2023, 12, 31, 0, 0, 0)
    end = datetime(2024, 1, 2, 0, 0, 0)
    candles = client.get_historical_ohlcv(
        "AAPL",
        Timeframe.FIFTEEN_MINUTES,
        start=start,
        end=end,
        limit=50,
    )

    assert len(candles) == 1
    params = session.calls[0]["params"]
    assert params["start_date"] == start.isoformat()
    assert params["end_date"] == end.isoformat()
    assert params["outputsize"] == 50
    assert params["interval"] == Timeframe.FIFTEEN_MINUTES.value


def test_get_latest_ohlcv_handles_http_error() -> None:
    session = MockSession(MockResponse({"message": "bad request"}, status_code=400))
    client = TwelveDataClient(api_key="fake", session=session, base_url="http://mock")

    with pytest.raises(DataProviderError):
        client.get_latest_ohlcv("AAPL", Timeframe.ONE_MINUTE, count=1)


def test_get_latest_ohlcv_handles_invalid_payload() -> None:
    session = MockSession(MockResponse({"unexpected": "payload"}))
    client = TwelveDataClient(api_key="fake", session=session, base_url="http://mock")

    with pytest.raises(DataProviderError):
        client.get_latest_ohlcv("AAPL", Timeframe.ONE_MINUTE, count=1)
