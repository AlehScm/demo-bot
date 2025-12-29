from pydantic import BaseModel
from typing import List

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