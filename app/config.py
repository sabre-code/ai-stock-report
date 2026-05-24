from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── LLM ───────────────────────────────────────────────────────────────────
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # ── Storage ───────────────────────────────────────────────────────────────
    reports_dir: Path = Path("reports")

    # ── Server ────────────────────────────────────────────────────────────────
    # Use 0.0.0.0 so the server binds on all interfaces inside Docker / ECS.
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Research limits ───────────────────────────────────────────────────────
    news_max_items: int = 15          # max news headlines to collect
    price_history_days: int = 365     # yfinance lookback in days
    sec_filings_max: int = 5          # max SEC filings to summarise


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
