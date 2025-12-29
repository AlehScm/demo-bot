from __future__ import annotations

from typing import List

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from application.policies.timeframe_policy import TimeframePolicy
from application.use_cases.fetch_historical_ohlcv import FetchHistoricalOHLCV
from application.use_cases.fetch_latest_ohlcv import FetchLatestOHLCV
from application.use_cases.generate_trading_decision import GenerateTradingDecision
from domain.exceptions.errors import DataProviderError
from domain.services.trend_detector import TrendDetector
from domain.value_objects.timeframe import Timeframe
from domain.value_objects.trend import TrendDirection
from infrastructure.config.settings import load_settings
from infrastructure.data_providers.twelve_data_client import TwelveDataClient
from infrastructure.storage.logging.logger import get_logger
from interfaces.controllers.market_data_controller import MarketDataController
from interfaces.controllers.trading_controller import TradingController
from .models import TradeResponse, CandleResponse as CandleResponseModel, MarketDataResponse



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
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
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
    trend_detector = TrendDetector()
    
    # Setup use cases
    generate_decision = GenerateTradingDecision(
        fetch_latest=fetch_latest,
        trend_detector=trend_detector,
    )
    
    # Setup controllers
    market_data_controller = MarketDataController(
        fetch_latest=fetch_latest,
        fetch_historical=fetch_historical,
    )
    trading_controller = TradingController(generate_decision=generate_decision)

    @app.get("/")
    async def serve_frontend():
        """Serve the main frontend page."""
        return FileResponse("static/index.html")

    @app.get("/api/candles", response_model=List[CandleResponseModel])
    async def get_candles(
        symbol: str = Query(..., description="Asset symbol (e.g., BTC/USD, AAPL)"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(200, ge=1, le=5000, description="Number of candles to fetch (default: 200 to save API calls)"),
    ) -> List[CandleResponseModel]:
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
            candles = market_data_controller.latest(symbol=symbol, timeframe=tf, count=count)
        except DataProviderError as e:
            logger.error("Data provider error: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e))

        # Convert to Lightweight Charts format (sorted by time ascending)
        result = [
            CandleResponseModel(
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

    @app.get("/api/market-data", response_model=MarketDataResponse)
    async def get_market_data(
        symbol: str = Query("BTC/USD", description="Asset symbol (e.g., BTC/USD, AAPL)"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(200, ge=1, le=5000, description="Number of candles to fetch"),
    ):
        """
        Endpoint combinado que retorna candles E decisões em uma única chamada.
        Isso economiza chamadas à API Twelve Data (apenas 1 chamada ao invés de 2).
        
        Retorna tanto os candles para o gráfico quanto as decisões do bot baseadas
        nos mesmos candles, evitando fazer duas chamadas separadas.
        """
        try:
            tf = Timeframe(timeframe)
        except ValueError:
            valid = [t.value for t in Timeframe]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe. Valid options: {valid}",
            )

        try:
            # Buscar candles (apenas UMA chamada à API)
            candles = market_data_controller.latest(symbol=symbol, timeframe=tf, count=count)
            candles_list = list(candles)
            
            if not candles_list:
                return MarketDataResponse(candles=[], decisions=[])
            
            # Converter candles para formato da API
            candles_response = [
                CandleResponseModel(
                    time=int(candle.timestamp.timestamp()),
                    open=float(candle.open),
                    high=float(candle.high),
                    low=float(candle.low),
                    close=float(candle.close),
                    volume=float(candle.volume),
                )
                for candle in reversed(candles_list)
            ]
            
            # Gerar decisões usando os mesmos candles (sem fazer outra chamada à API)
            # Criamos um detector temporário para análise
            temp_detector = TrendDetector()
            trend_result = temp_detector.analyze(candles_list)
            
            last_candle = candles_list[-1]
            current_price = float(last_candle.close)
            last_candle_time = int(last_candle.timestamp.timestamp())
            
            decisions_response: list[TradeResponse] = []
            
            # Strategy 1: Use trend analysis if confidence is sufficient
            if trend_result.confidence > 0.3:
                if trend_result.trend == TrendDirection.UP:
                    decisions_response.append(
                        TradeResponse(
                            time=last_candle_time,
                            type="buy",
                            price=current_price,
                            text=f"Tendência de alta (conf: {trend_result.confidence:.2f})",
                        )
                    )
                elif trend_result.trend == TrendDirection.DOWN:
                    decisions_response.append(
                        TradeResponse(
                            time=last_candle_time,
                            type="sell",
                            price=current_price,
                            text=f"Tendência de queda (conf: {trend_result.confidence:.2f})",
                        )
                    )
            else:
                # Strategy 2: Fallback to simple momentum analysis
                if len(candles_list) >= 20:
                    recent_prices = [float(c.close) for c in candles_list[-10:]]
                    previous_prices = [float(c.close) for c in candles_list[-20:-10]]
                    recent_avg = sum(recent_prices) / len(recent_prices)
                    previous_avg = sum(previous_prices) / len(previous_prices)
                    
                    if recent_avg > previous_avg * 1.001:
                        percent_change = ((recent_avg / previous_avg - 1) * 100)
                        decisions_response.append(
                            TradeResponse(
                                time=last_candle_time,
                                type="buy",
                                price=current_price,
                                text=f"Momentum positivo (+{percent_change:.2f}%)",
                            )
                        )
                    elif recent_avg < previous_avg * 0.999:
                        percent_change = ((recent_avg / previous_avg - 1) * 100)
                        decisions_response.append(
                            TradeResponse(
                                time=last_candle_time,
                                type="sell",
                                price=current_price,
                                text=f"Momentum negativo ({percent_change:.2f}%)",
                            )
                        )
            
            logger.info("Generated %d candles and %d decisions for symbol %s", 
                       len(candles_response), len(decisions_response), symbol)
            
            return MarketDataResponse(
                candles=candles_response,
                decisions=decisions_response
            )
            
        except DataProviderError as e:
            logger.error("Data provider error in get_market_data: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            logger.error("Error in get_market_data: %s", str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/bot/decisions", response_model=List[TradeResponse])
    async def get_decisions(
        symbol: str = Query("BTC/USD", description="Asset symbol (e.g., BTC/USD, AAPL)"),
        timeframe: str = Query("1min", description="Candle timeframe"),
    ):
        """
        Retorna as operações que o bot 'decidiu' executar baseado na análise de tendência.
        
        NOTA: Este endpoint faz UMA chamada à API Twelve Data (200 candles para análise).
        Para economizar chamadas à API, use o endpoint /api/market-data que retorna
        candles + decisões em uma única chamada.
        """
        try:
            tf = Timeframe(timeframe)
        except ValueError:
            valid = [t.value for t in Timeframe]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe. Valid options: {valid}",
            )

        try:
            # Use controller to get trading decisions
            # O use case já busca os candles necessários (200 por padrão)
            decisions = trading_controller.get_decisions(symbol=symbol, timeframe=tf)
            
            # Convert domain decisions to API response model
            result = [
                TradeResponse(
                    time=decision.time,
                    type=decision.type,
                    price=decision.price,
                    text=decision.text,
                )
                for decision in decisions
            ]
            
            logger.info("Generated %d decisions for symbol %s", len(result), symbol)
            return result
            
        except DataProviderError as e:
            logger.error("Data provider error in get_decisions: %s", str(e))
            return []
        except Exception as e:
            logger.error("Error generating bot decisions: %s", str(e))
            return []

    return app


app = create_app()

