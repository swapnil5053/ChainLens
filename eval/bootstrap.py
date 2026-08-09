"""Shared bootstrap for evaluation entry points.

Puts the API package on the path and, when asked, starts the local PostgreSQL used in
environments without Docker. Importing has no side effects beyond the path change; the
server start is an explicit call.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
for entry in (str(API), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

LOCAL_PGDATA = ROOT / "var" / "pgdata"


def ensure_database() -> str:
    """Return a usable DSN, starting a local server if configured to.

    ``CHAINLENS_LOCAL_PG=1`` starts an embedded PostgreSQL 16 in this process. The
    embedded server does not survive between commands, so each entry point brings it up
    itself. In production the DSN
    comes from the environment and this function does nothing.
    """
    # Load a .env at the repo root, if present, so the database URL and the Gemini key can
    # live in a file rather than being exported by hand each session. Values already in the
    # real environment win over the file.
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except ImportError:  # pragma: no cover - python-dotenv is a transitive dependency
        pass

    if os.environ.get("CHAINLENS_LOCAL_PG") == "1":
        import pgserver

        LOCAL_PGDATA.mkdir(parents=True, exist_ok=True)
        server = pgserver.get_server(LOCAL_PGDATA, cleanup_mode=None)  # type: ignore[attr-defined]
        server.psql("CREATE EXTENSION IF NOT EXISTS vector;")
        dsn = str(server.get_uri()).replace("postgresql://", "postgresql+psycopg://")
        os.environ["CHAINLENS_DATABASE_URL"] = dsn
        return dsn
    return os.environ.get(
        "CHAINLENS_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/chainlens"
    )
