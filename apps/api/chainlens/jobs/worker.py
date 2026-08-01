"""arq worker for asynchronous ingestion.

The API enqueues here when Redis is reachable and falls back to inline ingestion when it
is not, so a deployment without a worker still works, just synchronously. The state
machine is the same either way, because both paths call
``chainlens.ingest.pipeline.index_parsed_document`` and both write progress to the same
``jobs`` row.

Not exercised end to end in the environment this was written in: no Redis server was
installable. See docs/HANDOFF.md.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ..api.deps import build_services
from ..config import get_settings
from ..db.models import Job
from ..db.session import session_scope
from ..ingest.parse import parse_pdf
from ..ingest.pipeline import index_parsed_document
from ..logging import configure_logging, get_logger

logger = get_logger(__name__)


async def ingest_document(ctx: dict[str, Any], job_id: str, path: str) -> dict[str, Any]:
    services = ctx["services"]
    settings = services.settings
    identifier = uuid.UUID(job_id)

    with session_scope() as session:
        row = session.get(Job, identifier)
        if row is None:
            return {"error": "unknown job", "job_id": job_id}

        def progress(state: str, fraction: float, detail: str) -> None:
            row.state, row.progress, row.detail = state, fraction, detail
            session.flush()

        try:
            parsed = parse_pdf(Path(path), max_pages=settings.max_pdf_pages)
            result = index_parsed_document(
                session,
                parsed,
                embedder=services.embedder,
                chunk_strategy=settings.chunk_strategy,
                index_name=settings.chunk_strategy,
                byte_size=Path(path).stat().st_size,
                on_progress=progress,
            )
        except Exception as exc:
            row.state, row.error = "failed", f"{type(exc).__name__}: {exc}"
            logger.error("ingest_failed", job_id=job_id, error=row.error)
            return {"state": "failed", "error": row.error}

        row.document_id = result.document_id
        row.timings_ms = dict(result.timings_ms)
        return {
            "state": "ready",
            "document_id": str(result.document_id),
            "chunks": result.chunk_count,
        }


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    ctx["services"] = build_services(settings)


class WorkerSettings:
    functions = (ingest_document,)
    on_startup = startup
    max_jobs = 2
    job_timeout = 900

    @staticmethod
    def redis_settings() -> Any:
        from arq.connections import RedisSettings

        return RedisSettings.from_dsn(get_settings().redis_url)
