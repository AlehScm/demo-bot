from __future__ import annotations

from decimal import Decimal

from infrastructure.config.liquidity import load_liquidity_settings


def test_load_liquidity_settings_defaults(monkeypatch):
    for key in (
        "ACCUMULATION_MIN_CANDLES",
        "ACCUMULATION_MAX_RANGE_PERCENT",
        "ACCUMULATION_MIN_STRENGTH",
        "ACCUMULATION_MIN_BOUNDARY_TOUCHES",
        "ACCUMULATION_MAX_ZONES",
        "ACCUMULATION_MIN_GAP_BETWEEN_ZONES",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = load_liquidity_settings()

    assert settings.min_candles_in_zone == 25
    assert settings.max_range_percent == Decimal("0.8")
    assert settings.min_strength == 0.55
    assert settings.min_boundary_touches == 3
    assert settings.max_zones == 5
    assert settings.min_gap_between_zones == 15


def test_load_liquidity_settings_overrides(monkeypatch):
    monkeypatch.setenv("ACCUMULATION_MIN_CANDLES", "30")
    monkeypatch.setenv("ACCUMULATION_MAX_RANGE_PERCENT", "1.2")
    monkeypatch.setenv("ACCUMULATION_MIN_STRENGTH", "0.6")
    monkeypatch.setenv("ACCUMULATION_MIN_BOUNDARY_TOUCHES", "4")
    monkeypatch.setenv("ACCUMULATION_MAX_ZONES", "7")
    monkeypatch.setenv("ACCUMULATION_MIN_GAP_BETWEEN_ZONES", "20")

    settings = load_liquidity_settings()

    assert settings.min_candles_in_zone == 30
    assert settings.max_range_percent == Decimal("1.2")
    assert settings.min_strength == 0.6
    assert settings.min_boundary_touches == 4
    assert settings.max_zones == 7
    assert settings.min_gap_between_zones == 20
