"""Start the whole backend in one process: database, migrations, index, and the API.

Why this exists. On the Docker-free path the database and the web server were two
processes that could not find each other: ``ensure_database`` starts an embedded
PostgreSQL and sets the DSN in its own environment, but a separately launched ``uvicorn``
never saw it and fell back to a localhost server that was not there. Running everything
in one process fixes that; the app connects to exactly the database this script started.

It is also idempotent about setup: it migrates to head, and if the corpus has not been
indexed yet it fits the embedding model and indexes it, so a first run needs no separate
build step.

    CHAINLENS_LOCAL_PG=1 python scripts/serve.py
    CHAINLENS_LOCAL_PG=1 python scripts/serve.py --port 8000 --no-seed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.bootstrap import ensure_database


def _migrate(dsn: str) -> None:
    from alembic.config import Config

    from alembic import command

    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps" / "api" / "alembic"))
    config.set_main_option("sqlalchemy.url", dsn)
    command.upgrade(config, "head")


def _needs_index() -> bool:
    from sqlalchemy import text

    from chainlens.db.session import get_engine

    with get_engine().connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM documents")).scalar_one()
    return int(count) == 0


def _build_index() -> None:
    """Fit the embedding model on the corpus and index it, the same path eval uses."""
    from eval.build_index import STRATEGIES, fit_embedder, load_corpus  # noqa: F401

    from chainlens.db.session import session_scope
    from chainlens.ingest.parse import parse_text
    from chainlens.ingest.pipeline import index_parsed_document

    embedder = fit_embedder()
    corpus = load_corpus()
    with session_scope() as session:
        for name, raw in corpus:
            index_parsed_document(
                session,
                parse_text(raw, f"{name}.txt"),
                embedder=embedder,
                chunk_strategy="clause-aware",
                index_name="clause-aware",
                meta={"corpus": "cuad-supply-chain-subset"},
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-seed", action="store_true", help="do not index the corpus if empty")
    args = parser.parse_args()

    dsn = ensure_database()
    print(f"database ready: {dsn}", flush=True)
    _migrate(dsn)
    print("migrations applied", flush=True)

    if not args.no_seed and _needs_index():
        print("indexing the 29-contract corpus (about 30 seconds, first run only)...", flush=True)
        _build_index()
        print("corpus indexed", flush=True)

    import uvicorn

    print(f"serving on http://{args.host}:{args.port}  (open the web app pointed here)", flush=True)
    uvicorn.run("chainlens.main:app", host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
