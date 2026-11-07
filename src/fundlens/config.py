"""Runtime settings and ingestion scope configuration."""

from __future__ import annotations

import hashlib
import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = PROJECT_ROOT / "config" / "scope.toml"


@dataclass(frozen=True)
class Scope:
    start_date: date
    chunk_days: int
    plans: frozenset[str]
    options: frozenset[str]
    categories: dict[str, str]
    analysis_default_plan: str
    config_hash: str


def load_scope(path: Path = SCOPE_PATH) -> Scope:
    raw_bytes = path.read_bytes()
    cfg = tomllib.loads(raw_bytes.decode("utf-8"))
    return Scope(
        start_date=date.fromisoformat(cfg["history"]["start_date"]),
        chunk_days=int(cfg["history"]["chunk_days"]),
        plans=frozenset(p.upper() for p in cfg["plan"]["include"]),
        options=frozenset(o.upper() for o in cfg["option"]["include"]),
        categories={k.strip().lower(): v for k, v in cfg["categories"].items()},
        analysis_default_plan=cfg["plan"]["analysis_default"].upper(),
        config_hash=hashlib.sha256(raw_bytes).hexdigest(),
    )


def database_url() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env.")
    return url


def raw_data_dir() -> Path:
    load_dotenv(PROJECT_ROOT / ".env")
    return PROJECT_ROOT / os.environ.get("RAW_DATA_DIR", "data/raw")
