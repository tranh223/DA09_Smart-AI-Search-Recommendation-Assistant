from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv


PACKAGE_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "VinSmartFuture"
    user_profile_collection: str = "Users"
    bookings_collection: str = "Booking"
    postgres_dsn: str = ""
    hotel_api_base_url: str = ""
    hotel_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    rerank_temperature: float = 0.1
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    base_dir: Path = PACKAGE_ROOT


def _bool_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def postgres_debug_info(dsn: str) -> dict[str, str | bool | int | None]:
    if not dsn:
        return {"configured": False}
    parsed = urlparse(dsn)
    return {
        "configured": True,
        "scheme": parsed.scheme or None,
        "host": parsed.hostname or None,
        "port": parsed.port,
        "database": unquote(parsed.path.lstrip("/")) or None,
        "user": unquote(parsed.username) if parsed.username else None,
        "password_set": bool(parsed.password),
    }


def load_settings() -> Settings:
    load_dotenv(PACKAGE_ROOT / ".env")
    return Settings(
        
        mongodb_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        mongodb_db=os.getenv("DATABASE_NAME", "VinSmartFuture"),
        user_profile_collection=os.getenv("MONGODB_USER_PROFILE_COLLECTION", "Users"),
        bookings_collection=os.getenv("MONGODB_BOOKINGS_COLLECTION", "Booking"),
        postgres_dsn=os.getenv("POSTGRES_DSN", ""),
        hotel_api_base_url=os.getenv("HOTEL_API_BASE_URL", ""),
        hotel_api_key=os.getenv("HOTEL_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        rerank_temperature=float(os.getenv("RERANK_TEMPERATURE", "0.1") or "0.1"),
        llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "30") or "30"),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2") or "2"),
        base_dir=PACKAGE_ROOT,
    )
