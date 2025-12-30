from pydantic import BaseModel
from typing import List, Optional


class TradeResponse(BaseModel):
    """Modelo para as decisões que o bot visualiza no gráfico."""
    time: int
    type: str  # 'buy' ou 'sell'
    price: float
    text: str


class CandleResponse(BaseModel):
    """Candle data formatted for Lightweight Charts."""
    time: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataResponse(BaseModel):
    """Combined response with candles and trading decisions."""
    candles: List[CandleResponse]
    decisions: List[TradeResponse]


# ============ Indicator Models ============

class SwingPointResponse(BaseModel):
    """Swing point for chart markers (HH, HL, LL, LH)."""
    time: int  # Unix timestamp
    price: float
    type: str  # 'HH', 'HL', 'LL', 'LH', 'SH', 'SL'
    position: str  # 'aboveBar' or 'belowBar'
    color: str  # hex color
    shape: str  # 'arrowUp', 'arrowDown', 'circle'
    text: str  # label text


class BOSResponse(BaseModel):
    """Break of Structure for chart visualization."""
    type: str  # 'BULLISH' or 'BEARISH'
    broken_swing_time: int
    broken_swing_price: float
    break_time: int
    break_price: float
    color: str


class TrendIndicatorResponse(BaseModel):
    """Full trend indicator response for chart overlay."""
    trend: str  # 'UP', 'DOWN', 'UNDEFINED'
    confidence: float
    reason: str
    swings: List[SwingPointResponse]
    last_bos: Optional[BOSResponse] = None


# ============ Liquidity Indicator Models ============

class AccumulationZoneResponse(BaseModel):
    """Accumulation zone for chart rectangle visualization."""
    start_time: int  # Unix timestamp
    end_time: int  # Unix timestamp
    high_price: float
    low_price: float
    candle_count: int
    strength: float  # 0.0 to 1.0
    liquidity_sweeps: List[dict] = []
    range_break: dict | None = None


class LiquidityIndicatorResponse(BaseModel):
    """Full liquidity indicator response with accumulation zones."""
    accumulation_zones: List[AccumulationZoneResponse]
    total_zones: int


# ============ Unified Analysis Response ============

class TrendInfoResponse(BaseModel):
    """Simplified trend info (without swings for display)."""
    trend: str  # 'UP', 'DOWN', 'UNDEFINED'
    confidence: float
    reason: str


class FullAnalysisResponse(BaseModel):
    """
    Unified response containing candles and all indicator analyses.
    
    This endpoint makes only ONE call to the external API (Twelve Data)
    and runs all indicators locally on the same candle data.
    """
    candles: List[CandleResponse]
    trend: TrendInfoResponse
    accumulation_zones: List[AccumulationZoneResponse]
