"""
Trend indicator module.

Contains the trend indicator implementation for detecting market structure,
swing points (HH, HL, LL, LH), and Break of Structure (BOS).
"""

from domain.indicators.trend.models import (
    BOSType,
    BreakOfStructure,
    SwingClassification,
    SwingPoint,
    TrendSignal,
)
from domain.indicators.trend.trend_indicator import TrendIndicator

__all__ = [
    "BOSType",
    "BreakOfStructure",
    "SwingClassification",
    "SwingPoint",
    "TrendIndicator",
    "TrendSignal",
]

