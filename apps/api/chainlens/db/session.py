"""Engine and session construction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def get_engine(dsn: str | None = None) -> Engine:
    global _engine, _factory
    if _engine is None or dsn is not None:
        _engine = create_engine(dsn or get_settings().database_url, pool_pre_ping=True)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    get_engine()
    assert _factory is not None
    return _factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_extensions(engine: Engine | None = None) -> None:
    with (engine or get_engine()).begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def ping(engine: Engine | None = None) -> bool:
    with (engine or get_engine()).connect() as connection:
        return bool(connection.execute(text("SELECT 1")).scalar_one() == 1)
