from __future__ import annotations

from fastapi import APIRouter, Request

from ...db.session import ping
from ..schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness. Deliberately checks nothing external."""
    return HealthResponse(status="ok", version="2.0.0")


@router.get("/readyz", response_model=ReadyResponse)
def readyz(request: Request) -> ReadyResponse:
    """Readiness. Actually connects to Postgres and Redis rather than assuming."""
    services = request.app.state.services
    detail: dict[str, str] = {}

    try:
        postgres_ok = ping()
    except Exception as exc:
        postgres_ok = False
        detail["postgres"] = f"{type(exc).__name__}: {exc}"

    redis_ok = False
    try:
        import redis

        client = redis.Redis.from_url(services.settings.redis_url, socket_timeout=1.0)
        redis_ok = bool(client.ping())
    except Exception as exc:
        detail["redis"] = f"{type(exc).__name__}: {exc}"
        detail["redis_impact"] = "ingestion runs inline instead of on a worker"

    if services.embedder_error:
        detail["embedding"] = services.embedder_error
    if not services.generation.available:
        detail["generation"] = getattr(services.generation, "reason", "unavailable")
    if not services.reranker.available:
        detail["reranker"] = getattr(services.reranker, "error", None) or "unavailable"
        detail["reranker_impact"] = "retrieval degrades to fusion-only, and says so"

    return ReadyResponse(
        status="ready" if postgres_ok and services.embedder else "degraded",
        postgres=postgres_ok,
        redis=redis_ok,
        embedding_provider=services.embedder.name if services.embedder else None,
        reranker=services.reranker.name if services.reranker.available else "unavailable",
        generation=(services.generation.name if services.generation.available else "unavailable"),
        detail=detail,
    )
