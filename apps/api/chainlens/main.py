"""Application entry point."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.deps import build_services
from .api.limits import DocumentScope, RateLimiter
from .api.routers import documents, extraction, health, jobs, metrics, query
from .config import get_settings
from .logging import configure_logging, get_logger, request_id_var
from .paths import ensure_runtime_dirs

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    ensure_runtime_dirs()
    app.state.services = build_services(settings)
    app.state.rate_limiter = RateLimiter(
        default_per_minute=settings.rate_limit_per_minute,
        expensive_per_minute=settings.rate_limit_expensive_per_minute,
    )
    app.state.document_scope = DocumentScope(settings.parsed_document_scopes())
    logger.info(
        "startup",
        embedding=(app.state.services.embedder.name if app.state.services.embedder else None),
        generation=app.state.services.generation.name,
        chunk_strategy=settings.chunk_strategy,
        retrieval_strategy=settings.retrieval_strategy,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ChainLens",
        version="2.0.0",
        summary="Clause-level contract analysis for supply chain and logistics documents",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Per-client limiting, applied before any work is done.

        Health and readiness are exempt: a probe that trips the limit takes the service
        out of rotation for a reason that has nothing to do with its health.
        """
        limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
        if limiter is None or request.url.path in {"/health", "/readyz"}:
            return await call_next(request)
        try:
            _, remaining = limiter.enforce(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=dict(exc.headers or {}),
            )
        response = await call_next(request)
        response.headers["x-ratelimit-remaining"] = str(remaining)
        return response

    @app.middleware("http")
    async def attach_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request_id_var.set(request_id)
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    for router in (
        health.router,
        documents.router,
        jobs.router,
        query.router,
        extraction.router,
        metrics.router,
    ):
        app.include_router(router)
    return app


app = create_app()
