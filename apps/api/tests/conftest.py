"""Test fixtures.

Tests that need a database start a real PostgreSQL 16 with pgvector in-process when
``CHAINLENS_LOCAL_PG=1``, and are skipped otherwise. Tests that only need the pure
functions -- parsing, chunking, fusion, the groundedness guard -- have no dependencies
at all and always run.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def database_url() -> str:
    if os.environ.get("CHAINLENS_LOCAL_PG") != "1":
        pytest.skip("set CHAINLENS_LOCAL_PG=1 to run tests that need Postgres")
    import pgserver

    pgdata = ROOT / "var" / "pgdata"
    pgdata.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(pgdata, cleanup_mode=None)
    server.psql("CREATE EXTENSION IF NOT EXISTS vector;")
    dsn = server.get_uri().replace("postgresql://", "postgresql+psycopg://")
    os.environ["CHAINLENS_DATABASE_URL"] = dsn
    return dsn


@pytest.fixture()
def session(database_url: str) -> Iterator[object]:
    from chainlens.db.session import get_engine, session_scope

    get_engine(database_url)
    with session_scope() as active:
        yield active


@pytest.fixture(scope="session")
def sample_contract() -> str:
    corpus = ROOT / "eval" / "datasets" / "corpus"
    files = sorted(corpus.glob("*.txt"))
    if not files:
        pytest.skip("evaluation corpus is not present")
    return files[0].read_text(encoding="utf-8")
