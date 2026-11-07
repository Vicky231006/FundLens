"""Integration-test fixtures.

A migrated template database is built once per session; every test gets its own cheap clone
(``CREATE DATABASE ... TEMPLATE``). Only databases named ``fundlens_test_*`` are ever created
or dropped, never the working ``fundlens`` database.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from sqlalchemy.engine import make_url

from fundlens.config import database_url
from fundlens.db import apply_migrations, connect

TEMPLATE_DB = "fundlens_test_template"


def _url_for(db: str) -> str:
    return make_url(database_url()).set(database=db).render_as_string(hide_password=False)


def _admin() -> psycopg.Connection:
    return connect(autocommit=True, url=_url_for("postgres"))


@pytest.fixture(scope="session")
def template_db() -> Iterator[str]:
    try:
        admin = _admin()
    except psycopg.OperationalError as exc:  # pragma: no cover
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    with admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{TEMPLATE_DB}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{TEMPLATE_DB}"')
    apply_migrations(url=_url_for(TEMPLATE_DB))
    yield TEMPLATE_DB
    with _admin() as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{TEMPLATE_DB}" WITH (FORCE)')


@pytest.fixture()
def db_url(template_db: str) -> Iterator[str]:
    name = f"fundlens_test_{uuid.uuid4().hex[:10]}"
    with _admin() as admin:
        admin.execute(f'CREATE DATABASE "{name}" TEMPLATE "{template_db}"')
    try:
        yield _url_for(name)
    finally:
        with _admin() as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture()
def conn(db_url: str) -> Iterator[psycopg.Connection]:
    with connect(autocommit=True, url=db_url) as c:
        yield c
