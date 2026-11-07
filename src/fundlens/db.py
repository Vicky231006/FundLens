"""Database access helpers and the SQL migration runner."""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg
from sqlalchemy import Engine, create_engine

from fundlens.config import PROJECT_ROOT, database_url

log = logging.getLogger(__name__)
MIGRATIONS_DIR = PROJECT_ROOT / "sql" / "migrations"


def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def psycopg_dsn(url: str | None = None) -> str:
    return (url or database_url()).replace("postgresql+psycopg://", "postgresql://")


def connect(*, autocommit: bool = False, url: str | None = None) -> psycopg.Connection:
    """Plain psycopg connection (used for COPY-based bulk loading).

    With ``autocommit=True`` every ``conn.transaction()`` block is a real, independently
    committed transaction (without it, the block would only be a savepoint inside an
    outer transaction that is not committed until ``conn.commit()``).
    """
    return psycopg.connect(psycopg_dsn(url), autocommit=autocommit)


def apply_migrations(migrations_dir: Path = MIGRATIONS_DIR, url: str | None = None) -> list[str]:
    """Apply any unapplied ``NNN_name.sql`` files in order. Each runs in one transaction.

    Applied versions are tracked in ``public.schema_migration``; a changed checksum on an
    already-applied file is an error (migrations are append-only).
    """
    import hashlib

    applied_now: list[str] = []
    with connect(url=url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.schema_migration ("
            " version TEXT PRIMARY KEY, checksum TEXT NOT NULL,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        conn.commit()
        done = dict(conn.execute("SELECT version, checksum FROM public.schema_migration").fetchall())
        for path in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            if path.name in done:
                if done[path.name] != checksum:
                    raise RuntimeError(f"Migration {path.name} was modified after being applied")
                continue
            log.info("Applying migration %s", path.name)
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO public.schema_migration (version, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )
            applied_now.append(path.name)
    return applied_now
