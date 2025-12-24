from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum


class AppEnvironment(str, Enum):
    DEV = "DEV"
    PAPER = "PAPER"
    PROD = "PROD"


def _parse_log_level(value: str | None) -> int:
    if value is None:
        return logging.INFO

    if value.isdigit():
        return int(value)

    normalized = value.upper()
    return logging._nameToLevel.get(normalized, logging.INFO)


@dataclass(frozen=True)
class Settings:
    env: AppEnvironment
    api_key: str | None
    base_url: str | None
    log_level: int


def load_settings() -> Settings:
    env_value = os.getenv("APP_ENV", AppEnvironment.DEV.value).upper()
    try:
        env = AppEnvironment(env_value)
    except ValueError as exc:
        raise ValueError(f"Invalid APP_ENV value: {env_value}. Use DEV, PAPER, or PROD.") from exc

    api_key = os.getenv("TWELVEDATA_API_KEY")
    base_url = os.getenv("TWELVEDATA_BASE_URL")
    log_level = _parse_log_level(os.getenv("LOG_LEVEL"))

    return Settings(env=env, api_key=api_key, base_url=base_url, log_level=log_level)
