"""Question answering, with and without streaming.

The SSE phase events are driven by real backend timings rather than a timer: each event
carries the measured milliseconds for the phase that just finished, so the interface
cannot show a "reranking" step that did not happen.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ...db.models import Query
from ...db.session import session_scope
from ...generation.guard import check_groundedness
from ...generation.prompt import SYSTEM_PROMPT, build_user_prompt, prompt_hash
from ...generation.provider import GenerationUnavailable
from ...logging import get_logger, request_id_var
from ...retrieval.service import RetrievalConfig
from ...retrieval.types import RetrievedChunk
from ..schemas import CitationModel, PageSpanModel, QueryRequest, QueryResponse

router = APIRouter(tags=["query"])
logger = get_logger(__name__)


def _citations(chunks: list[RetrievedChunk]) -> list[CitationModel]:
    return [
        CitationModel(
            index=index,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page=chunk.page,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            page_char_start=chunk.page_char_start,
            page_char_end=chunk.page_char_end,
            page_spans=[PageSpanModel(**span) for span in chunk.page_spans],
            clause_id=chunk.clause_id,
            clause_title=chunk.clause_title,
            score=round(chunk.score, 6),
            ranks=chunk.ranks,
            text=chunk.text,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _config(request: Request, body: QueryRequest) -> RetrievalConfig:
    base = RetrievalConfig.from_settings(request.app.state.services.settings)
    overrides: dict[str, object] = {}
    if body.k is not None:
        overrides["k"] = body.k
    if body.strategy is not None:
        overrides["strategy"] = body.strategy
    return RetrievalConfig(**(base.to_dict() | overrides))


def _record(
    request_id: str,
    body: QueryRequest,
    config: RetrievalConfig,
    embed_ms: float,
    retrieval_ms: float,
    rerank_ms: float,
    generation_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
) -> None:
    with session_scope() as session:
        session.add(
            Query(
                request_id=request_id,
                document_id=body.document_id,
                question=body.question,
                config_hash=config.hash,
                embed_ms=embed_ms,
                retrieval_ms=retrieval_ms,
                rerank_ms=rerank_ms,
                generation_ms=generation_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
            )
        )


@router.post("/query", response_model=QueryResponse)
def query(request: Request, body: QueryRequest) -> QueryResponse:
    services = request.app.state.services
    if services.retrieval is None:
        raise HTTPException(
            status_code=503, detail=services.embedder_error or "retrieval is unavailable"
        )
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    config = _config(request, body)

    with session_scope() as session:
        chunks, trace = services.retrieval.search(
            session, body.question, config=config, document_id=body.document_id
        )

    answer: str | None = None
    answer_status = "unavailable"
    answer_detail: str | None = None
    generation_ms = 0.0
    usage = services.generation.usage()
    if services.generation.available:
        started = time.perf_counter()
        try:
            answer = "".join(
                services.generation.stream(SYSTEM_PROMPT, build_user_prompt(body.question, chunks))
            )
            answer_status = "ok"
        except Exception as exc:
            answer_status = "error"
            answer_detail = f"{type(exc).__name__}: {exc}"
        generation_ms = (time.perf_counter() - started) * 1000
        usage = services.generation.usage()
    else:
        answer_detail = getattr(services.generation, "reason", "no generation provider")

    _record(
        request_id,
        body,
        config,
        trace.embed_ms,
        trace.total_ms - trace.rerank_ms - trace.embed_ms,
        trace.rerank_ms,
        generation_ms,
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.cost_usd,
    )
    logger.info("query", strategy=config.strategy, citations=len(chunks))

    return QueryResponse(
        request_id=request_id,
        question=body.question,
        answer=answer,
        answer_status=answer_status,
        answer_detail=answer_detail,
        citations=_citations(chunks),
        trace=trace.to_dict() | {"prompt_hash": prompt_hash()},
        groundedness=(check_groundedness(answer, len(chunks)).to_dict() if answer else None),
        config_hash=config.hash,
    )


@router.post("/query/stream")
def query_stream(request: Request, body: QueryRequest) -> EventSourceResponse:
    services = request.app.state.services
    if services.retrieval is None:
        raise HTTPException(
            status_code=503, detail=services.embedder_error or "retrieval is unavailable"
        )
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    config = _config(request, body)

    def events() -> Iterator[dict[str, str]]:
        yield {"event": "phase", "data": json.dumps({"phase": "retrieving"})}
        with session_scope() as session:
            chunks, trace = services.retrieval.search(
                session, body.question, config=config, document_id=body.document_id
            )
        yield {
            "event": "phase",
            "data": json.dumps(
                {
                    "phase": "reranking",
                    "ran": trace.reranker_available,
                    "ms": round(trace.rerank_ms, 2),
                    "note": (
                        None
                        if trace.reranker_available
                        else "reranker unavailable, fusion order kept"
                    ),
                }
            ),
        }
        yield {
            "event": "citations",
            "data": json.dumps(
                [citation.model_dump(mode="json") for citation in _citations(chunks)]
            ),
        }
        yield {
            "event": "phase",
            "data": json.dumps({"phase": "generating", "retrieval_ms": trace.total_ms}),
        }

        answer_parts: list[str] = []
        started = time.perf_counter()
        try:
            for token in services.generation.stream(
                SYSTEM_PROMPT, build_user_prompt(body.question, chunks)
            ):
                answer_parts.append(token)
                yield {"event": "token", "data": json.dumps({"text": token})}
        except GenerationUnavailable as exc:
            yield {"event": "answer_unavailable", "data": json.dumps({"reason": str(exc)})}
        except Exception as exc:  # pragma: no cover - upstream failure
            yield {
                "event": "error",
                "data": json.dumps({"error": f"{type(exc).__name__}: {exc}"}),
            }
        generation_ms = (time.perf_counter() - started) * 1000

        answer = "".join(answer_parts)
        usage = services.generation.usage()
        _record(
            request_id,
            body,
            config,
            trace.total_ms - trace.rerank_ms,
            trace.rerank_ms,
            generation_ms,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.cost_usd,
        )
        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "phase": "done",
                    "request_id": request_id,
                    "config_hash": config.hash,
                    "trace": trace.to_dict(),
                    "generation_ms": round(generation_ms, 2),
                    "groundedness": (
                        check_groundedness(answer, len(chunks)).to_dict() if answer else None
                    ),
                }
            ),
        }

    return EventSourceResponse(events())
