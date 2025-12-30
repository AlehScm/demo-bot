from __future__ import annotations

from typing import List

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from application.policies.timeframe_policy import TimeframePolicy
from application.use_cases.detect_liquidity_zones import DetectLiquidityZones
from application.use_cases.fetch_historical_ohlcv import FetchHistoricalOHLCV
from application.use_cases.fetch_latest_ohlcv import FetchLatestOHLCV
from application.use_cases.generate_trading_decision import GenerateTradingDecision
from domain.exceptions.errors import DataProviderError
from domain.indicators.trend import TrendIndicator, SwingClassification
from domain.services.trend_detector import TrendDetector
from domain.value_objects.timeframe import Timeframe
from domain.value_objects.trend import TrendDirection
from infrastructure.config.liquidity import load_liquidity_settings
from infrastructure.config.settings import load_settings
from infrastructure.data_providers.twelve_data_client import TwelveDataClient
from infrastructure.storage.cache.candle_cache import CandleCache
from infrastructure.storage.logging.logger import get_logger
from interfaces.controllers.market_data_controller import MarketDataController
from interfaces.controllers.trading_controller import TradingController
from interfaces.controllers.liquidity_controller import LiquidityController
from .models import (
    TradeResponse, 
    CandleResponse as CandleResponseModel, 
    MarketDataResponse,
    SwingPointResponse,
    BOSResponse,
    TrendIndicatorResponse,
    AccumulationZoneResponse,
    LiquidityIndicatorResponse,
    TrendInfoResponse,
    FullAnalysisResponse,
)



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
    candle_cache = CandleCache(cache_file=".cache/candles.json")
    fetch_latest = FetchLatestOHLCV(
        market_data_service=data_provider,
        timeframe_policy=timeframe_policy,
    )
    fetch_historical = FetchHistoricalOHLCV(
        market_data_service=data_provider,
        timeframe_policy=timeframe_policy,
    )
    trend_detector = TrendDetector()
    liquidity_settings = load_liquidity_settings()
    
    # Setup use cases
    generate_decision = GenerateTradingDecision(
        fetch_latest=fetch_latest,
        trend_detector=trend_detector,
    )
    detect_liquidity_zones = DetectLiquidityZones(liquidity_settings=liquidity_settings)
    
    # Setup controllers
    market_data_controller = MarketDataController(
        fetch_latest=fetch_latest,
        fetch_historical=fetch_historical,
        candle_cache=candle_cache,
    )
    trading_controller = TradingController(generate_decision=generate_decision)
    liquidity_controller = LiquidityController(detect_liquidity_zones=detect_liquidity_zones)

    @app.get("/api/candles", response_model=List[CandleResponseModel])
    async def get_candles(
        symbol: str = Query(..., description="Asset symbol (e.g., BTC/USD, AAPL)"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(5000, ge=1, le=5000, description="Number of candles to fetch (default: 5000)"),
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

    logger.info("FastAPI app created successfully")

    @app.get("/api/market-data", response_model=MarketDataResponse)
    async def get_market_data(
        symbol: str = Query("BTC/USD", description="Asset symbol (e.g., BTC/USD, AAPL)"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(5000, ge=1, le=5000, description="Number of candles to fetch"),
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

    @app.get("/api/indicators/trend", response_model=TrendIndicatorResponse)
    async def get_trend_indicator(
        symbol: str = Query("BTC/USD", description="Asset symbol"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(5000, ge=50, le=5000, description="Number of candles to analyze"),
    ):
        """
        Retorna análise de tendência com swings (HH, HL, LL, LH) e BOS.
        
        Os dados são formatados para exibição direta no gráfico:
        - swings: markers para HH/HL/LL/LH
        - last_bos: última quebra de estrutura detectada
        - trend: direção da tendência (UP, DOWN, UNDEFINED)
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
            # Fetch candles
            candles = market_data_controller.latest(symbol=symbol, timeframe=tf, count=count)
            candles_list = list(candles)
            
            if len(candles_list) < 10:
                return TrendIndicatorResponse(
                    trend="UNDEFINED",
                    confidence=0.0,
                    reason="Dados insuficientes para análise",
                    swings=[],
                    last_bos=None,
                )
            
            # Reverse to have oldest first (chronological order)
            candles_list = list(reversed(candles_list))
            
            # Run trend indicator
            trend_indicator = TrendIndicator()
            signal = trend_indicator.analyze(candles_list)
            
            # Convert swings to response format with chart styling
            swings_response: List[SwingPointResponse] = []
            for swing in signal.swings:
                # Determine color and position based on classification
                if swing.classification == SwingClassification.HIGHER_HIGH:
                    color = "#22c55e"  # green
                    position = "aboveBar"
                    shape = "arrowUp"
                    text = "HH"
                elif swing.classification == SwingClassification.HIGHER_LOW:
                    color = "#22c55e"  # green
                    position = "belowBar"
                    shape = "arrowUp"
                    text = "HL"
                elif swing.classification == SwingClassification.LOWER_LOW:
                    color = "#ef4444"  # red
                    position = "belowBar"
                    shape = "arrowDown"
                    text = "LL"
                elif swing.classification == SwingClassification.LOWER_HIGH:
                    color = "#ef4444"  # red
                    position = "aboveBar"
                    shape = "arrowDown"
                    text = "LH"
                elif swing.classification == SwingClassification.SWING_HIGH:
                    color = "#a855f7"  # purple
                    position = "aboveBar"
                    shape = "circle"
                    text = "SH"
                else:  # SWING_LOW
                    color = "#a855f7"  # purple
                    position = "belowBar"
                    shape = "circle"
                    text = "SL"
                
                swings_response.append(SwingPointResponse(
                    time=int(swing.timestamp.timestamp()),
                    price=float(swing.price),
                    type=swing.classification.value,
                    position=position,
                    color=color,
                    shape=shape,
                    text=text,
                ))
            
            # Convert BOS to response format
            bos_response = None
            if signal.last_bos:
                bos = signal.last_bos
                bos_response = BOSResponse(
                    type=bos.type.value,
                    broken_swing_time=int(bos.broken_swing.timestamp.timestamp()),
                    broken_swing_price=float(bos.broken_swing.price),
                    break_time=int(bos.break_timestamp.timestamp()),
                    break_price=float(bos.break_price),
                    color="#22c55e" if bos.is_bullish else "#ef4444",
                )
            
            logger.info(
                "Trend indicator for %s: %s (confidence: %.2f, swings: %d)",
                symbol, signal.trend.value, signal.confidence, len(swings_response)
            )
            
            return TrendIndicatorResponse(
                trend=signal.trend.value,
                confidence=signal.confidence,
                reason=signal.reason,
                swings=swings_response,
                last_bos=bos_response,
            )
            
        except DataProviderError as e:
            logger.error("Data provider error in trend indicator: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            logger.error("Error in trend indicator: %s", str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/indicators/liquidity", response_model=LiquidityIndicatorResponse)
    async def get_liquidity_indicator(
        symbol: str = Query("BTC/USD", description="Asset symbol"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(5000, ge=50, le=5000, description="Number of candles to analyze"),
    ):
        """
        Retorna zonas de acumulação (Wyckoff simplificado).
        
        Detecta áreas onde o preço está lateralizado em um range,
        indicando possível acumulação antes de um movimento.
        
        Retorna retângulos para desenhar no gráfico:
        - start_time/end_time: período da zona
        - high_price/low_price: limites do range
        - strength: força da acumulação (0-1)
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
            # Fetch candles
            candles = market_data_controller.latest(symbol=symbol, timeframe=tf, count=count)
            candles_list = list(candles)
            
            if len(candles_list) < liquidity_settings.min_candles_in_zone:
                return LiquidityIndicatorResponse(
                    accumulation_zones=[],
                    total_zones=0,
                )
            
            # Reverse to have oldest first (chronological order)
            candles_list = list(reversed(candles_list))
            
            # Run liquidity indicator via use case/controller
            signal = liquidity_controller.analyze(candles_list)
            
            # Convert accumulation zones to response format
            zones_response: List[AccumulationZoneResponse] = []
            for zone in signal.accumulation_zones:
                zones_response.append(AccumulationZoneResponse(
                    start_time=int(zone.start_time.timestamp()),
                    end_time=int(zone.end_time.timestamp()),
                    high_price=float(zone.high_price),
                    low_price=float(zone.low_price),
                    candle_count=zone.candle_count,
                    strength=zone.strength,
                    liquidity_sweeps=[{
                        "start_time": int(sweep.start_time.timestamp()),
                        "end_time": int(sweep.end_time.timestamp()),
                        "direction": sweep.direction.value,
                        "penetration_percent": sweep.penetration_percent,
                        "candle_count": sweep.candle_count,
                    } for sweep in zone.liquidity_sweeps],
                    range_break=None if zone.range_break is None else {
                        "start_time": int(zone.range_break.start_time.timestamp()),
                        "end_time": int(zone.range_break.end_time.timestamp()),
                        "direction": zone.range_break.direction.value,
                        "penetration_percent": zone.range_break.penetration_percent,
                        "candle_count": zone.range_break.candle_count,
                        "closes_outside": zone.range_break.closes_outside,
                    },
                ))
            
            logger.info(
                "Liquidity indicator for %s: %d accumulation zones detected",
                symbol, len(zones_response)
            )
            
            return LiquidityIndicatorResponse(
                accumulation_zones=zones_response,
                total_zones=len(zones_response),
            )
            
        except DataProviderError as e:
            logger.error("Data provider error in liquidity indicator: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            logger.error("Error in liquidity indicator: %s", str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/analysis", response_model=FullAnalysisResponse)
    async def get_full_analysis(
        symbol: str = Query("BTC/USD", description="Asset symbol"),
        timeframe: str = Query("1min", description="Candle timeframe"),
        count: int = Query(5000, ge=50, le=5000, description="Number of candles to analyze"),
    ):
        """
        Endpoint unificado que retorna candles e todas as análises de indicadores.
        
        OTIMIZAÇÃO: Faz apenas UMA chamada à API externa (Twelve Data) e roda
        todos os indicadores localmente nos mesmos candles.
        
        Retorna:
        - candles: Dados OHLCV para o gráfico
        - trend: Análise de tendência (UP, DOWN, UNDEFINED)
        - accumulation_zones: Zonas de acumulação detectadas
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
            # ===== UMA ÚNICA CHAMADA À API EXTERNA =====
            candles = market_data_controller.latest(symbol=symbol, timeframe=tf, count=count)
            candles_list = list(candles)
            
            if len(candles_list) < 10:
                return FullAnalysisResponse(
                    candles=[],
                    trend=TrendInfoResponse(
                        trend="UNDEFINED",
                        confidence=0.0,
                        reason="Dados insuficientes para análise",
                    ),
                    accumulation_zones=[],
                )
            
            # Converter candles para formato da API (ordenado cronologicamente)
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
            
            # Candles em ordem cronológica para os indicadores
            candles_chronological = list(reversed(candles_list))
            
            # ===== ANÁLISE DE TENDÊNCIA (local, sem chamada externa) =====
            trend_indicator = TrendIndicator()
            trend_signal = trend_indicator.analyze(candles_chronological)
            
            trend_response = TrendInfoResponse(
                trend=trend_signal.trend.value,
                confidence=trend_signal.confidence,
                reason=trend_signal.reason,
            )
            
            # ===== ANÁLISE DE LIQUIDEZ (local, sem chamada externa) =====
            liquidity_signal = liquidity_controller.analyze(candles_chronological)
            
            zones_response: List[AccumulationZoneResponse] = []
            for zone in liquidity_signal.accumulation_zones:
                zones_response.append(AccumulationZoneResponse(
                    start_time=int(zone.start_time.timestamp()),
                    end_time=int(zone.end_time.timestamp()),
                    high_price=float(zone.high_price),
                    low_price=float(zone.low_price),
                    candle_count=zone.candle_count,
                    strength=zone.strength,
                    liquidity_sweeps=[{
                        "start_time": int(sweep.start_time.timestamp()),
                        "end_time": int(sweep.end_time.timestamp()),
                        "direction": sweep.direction.value,
                        "penetration_percent": sweep.penetration_percent,
                        "candle_count": sweep.candle_count,
                    } for sweep in zone.liquidity_sweeps],
                    range_break=None if zone.range_break is None else {
                        "start_time": int(zone.range_break.start_time.timestamp()),
                        "end_time": int(zone.range_break.end_time.timestamp()),
                        "direction": zone.range_break.direction.value,
                        "penetration_percent": zone.range_break.penetration_percent,
                        "candle_count": zone.range_break.candle_count,
                        "closes_outside": zone.range_break.closes_outside,
                    },
                ))
            
            logger.info(
                "Full analysis for %s: trend=%s (%.2f), %d accumulation zones",
                symbol, trend_signal.trend.value, trend_signal.confidence, len(zones_response)
            )
            
            return FullAnalysisResponse(
                candles=candles_response,
                trend=trend_response,
                accumulation_zones=zones_response,
            )
            
        except DataProviderError as e:
            logger.error("Data provider error in full analysis: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            logger.error("Error in full analysis: %s", str(e))
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()
