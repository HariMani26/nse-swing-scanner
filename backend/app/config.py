"""Application configuration loaded from environment variables (.env)."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/nse_scanner.db"

    market_data_provider: str = "mock"  # mock | yfinance
    market_data_api_key: str = ""

    news_provider: str = "mock"  # mock | rss
    news_api_key: str = ""

    cache_ttl_seconds: int = 900
    rate_limit_max_calls: int = 5
    rate_limit_period_seconds: float = 1.0
    rate_limit_max_retries: int = 3

    scan_timezone: str = "Asia/Kolkata"
    scan_schedule_hour: int = 16
    scan_schedule_minute: int = 0
    enable_scheduler: bool = True

    market_open_time: str = "09:15"
    market_close_time: str = "15:30"

    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
