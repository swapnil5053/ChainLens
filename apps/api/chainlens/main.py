"""Application entry point."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .api.deps import build_services
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
