from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from application.policies.timeframe_policy import TimeframePolicy
from application.use_cases.fetch_latest_ohlcv import FetchLatestOHLCV
from application.use_cases.fetch_historical_ohlcv import FetchHistoricalOHLCV
from domain.exceptions.errors import DataProviderError
from domain.value_objects.timeframe import Timeframe
from infrastructure.config.settings import load_settings
from infrastructure.data_providers.twelve_data_client import TwelveDataClient
from infrastructure.storage.logging.logger import get_logger


class CandleResponse(BaseModel):
    """Candle data formatted for Lightweight Charts."""
    time: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = load_settings()
    logger = get_logger(__name__, level=settings.log_level)

    if not settings.api_key:
        raise ValueError("TWELVEDATA_API_KEY environment variable is required")

    app = FastAPI(
        title="Demo Bot API",
        description="API para dados de mercado com visualização em Lightweight Charts",
        version="1.0.0",
    )

    # Setup dependencies
    timeframe_policy = TimeframePolicy()
    data_provider = TwelveDataClient(
        api_key=settings.api_key,
        base_url=settings.base_url or "https://api.twelvedata.com",
    )
    fetch_latest = FetchLatestOHLCV(
        market_data_service=data_provider,
        timeframe_policy=timeframe_policy,
    )
    fetch_historical = FetchHistoricalOHLCV(
        market_data_service=data_provider,
        timeframe_policy=timeframe_policy,
    )

    @app.get("/")
    async def serve_frontend():
        """Serve the main frontend page."""
        return FileResponse("static/index.html")

    @app.get("/api/candles", response_model=List[CandleResponse])
    async def get_candles(
        symbol: str = Query(..., description="Asset symbol (e.g., BTC/USD, AAPL)"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(5000, ge=1, description="Number of candles to fetch"),
    ) -> List[CandleResponse]:
        """Fetch OHLCV candles for a given symbol and timeframe."""
        try:
            tf = Timeframe(timeframe)
        except ValueError:
            valid = [t.value for t in Timeframe]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe. Valid options: {valid}",
            )

        try:
            candles = fetch_latest.execute(symbol=symbol, timeframe=tf, count=count)
        except DataProviderError as e:
            logger.error("Data provider error: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e))

        # Convert to Lightweight Charts format (sorted by time ascending)
        result = [
            CandleResponse(
                time=int(candle.timestamp.timestamp()),
                open=float(candle.open),
                high=float(candle.high),
                low=float(candle.low),
                close=float(candle.close),
                volume=float(candle.volume),
            )
            for candle in reversed(list(candles))
        ]

        return result

    @app.get("/api/timeframes")
    async def get_timeframes():
        """Return available timeframes."""
        return [{"value": tf.value, "label": tf.value} for tf in Timeframe]

    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    logger.info("FastAPI app created successfully")
    return app


app = create_app()

