"""Configuration loaded from environment variables / a .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    # Comma-separated Telegram user ids, e.g. "123456,987654".
    admin_ids: Annotated[list[int], NoDecode] = []
    db_path: str = "data/shop.db"
    shop_name: str = "Maple & Pine Goods"
    currency_symbol: str = "$"
    timezone: str = "UTC"
    log_level: str = "INFO"
    # Messages per second for /broadcast. Telegram allows about 30/s globally.
    broadcast_rate: float = 20.0
    # Bank details shown to customers who pay by transfer; empty hides that payment option.
    # In .env write a line break as a backslash followed by n.
    payment_details: str = ""
    # Optional Google Sheets integration; it is on only when both the sheet id and the key file are set.
    google_sheet_id: str = ""
    google_service_account_file: str = ""
    sheets_sync_seconds: int = Field(default=60, ge=10)
    sheets_menu_sync: bool = True
    # Public demo: visitors can place test orders and see what the shop owner would receive.
    demo_mode: bool = False
    demo_max_orders_per_day: int = Field(default=5, ge=1)
    # Seconds until a visitor's new order moves to the next status by itself; 0 turns it off.
    demo_status_seconds: int = Field(default=60, ge=0)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(p) for p in value.replace(";", ",").split(",") if p.strip()]
        return [int(v) for v in value]

    @field_validator("payment_details")
    @classmethod
    def _unescape_newlines(cls, value: str) -> str:
        return value.replace("\\n", "\n").strip()

    @property
    def sheets_enabled(self) -> bool:
        return bool(self.google_sheet_id.strip() and self.google_service_account_file.strip())

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
