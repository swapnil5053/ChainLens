"""Start a local PostgreSQL 16 with pgvector, without Docker.

The production path is `infra/docker-compose.yml`. This exists because the environment
this repository was rebuilt in had no Docker daemon and no root, and the evaluation
harness still had to run against real Postgres rather than a substitute. See ADR-0001.

    eval "$(python scripts/local_postgres.py --export)"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

DATA_DIR = ROOT / "var" / "pgdata"


def start() -> str:
    import pgserver

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(DATA_DIR, cleanup_mode=None)  # type: ignore[attr-defined]
    server.psql("CREATE EXTENSION IF NOT EXISTS vector;")
    return server.get_uri().replace("postgresql://", "postgresql+psycopg://")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true", help="print a shell export")
    args = parser.parse_args()
    dsn = start()
    print(f"export CHAINLENS_DATABASE_URL='{dsn}'" if args.export else dsn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
