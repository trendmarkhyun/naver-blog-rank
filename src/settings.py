"""환경 변수 로드."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Settings:
    headless: bool
    max_rank: int
    delay_min: float
    delay_max: float
    max_retries: int
    db_path: Path
    log_dir: Path


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    db_path = os.getenv("DB_PATH", "data/rankings.db")
    log_dir = os.getenv("LOG_DIR", "logs")

    return Settings(
        headless=_env_bool("HEADLESS", True),
        max_rank=int(os.getenv("MAX_RANK", "50")),
        delay_min=float(os.getenv("DELAY_MIN", "3")),
        delay_max=float(os.getenv("DELAY_MAX", "8")),
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        db_path=PROJECT_ROOT / db_path,
        log_dir=PROJECT_ROOT / log_dir,
    )
