"""The view-facing surface, mounted at /web.

A separate router rather than a retrofit of the internal endpoints, for two reasons. The
internal `/documents` and `/compare` already mean something else and serve a different
consumer, and collapsing two meanings onto one path is how an API becomes impossible to
change. And the interface needs payload shapes chosen for a screen -- a contract list that
already knows its clause count, a comparison that carries the corpus evidence beside each
arm -- which are view concerns, not storage concerns.

Every response here matches, field for field, the zod schemas in
`apps/web/src/api/contracts.ts`. That file is the contract; this file satisfies it. The
`source` discriminator is set to "http" so the interface footer can say LIVE and mean it.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from ...db.models import Chunk, Document, Query
from ...db.session import session_scope
from ...generation.prompt import SYSTEM_PROMPT, build_user_prompt
from ...ingest.parse import parse_pdf_bytes
from ...ingest.pipeline import index_parsed_document
from ...logging import get_logger, request_id_var
from ...retrieval.service import RetrievalConfig
from ...retrieval.types import RetrievedChunk

router = APIRouter(prefix="/web", tags=["web"])
logger = get_logger(__name__)

# The two configurations the comparison screen contrasts, and the committed runs whose
# metrics describe them. The numbers are read from eval/results at request time rather
# than hardcoded, so the screen cannot drift from the artifacts.
ARM_RUNS = {
    "mmr": "clause-aware__mmr",
    "clause-rrf-expansion": "clause-aware__rrf_expansion",
}
REFERENCE_RUN = "recursive-512__mmr"

ARM_CONFIGS: dict[str, dict[str, Any]] = {
    "mmr": {
        "id": "mmr",
        "label": "MMR baseline",
        "chunking": "clause-aware",
        "strategy": "dense + MMR, lambda 0.5",
        "expansion": False,
    },
    "clause-rrf-expansion": {
        "id": "clause-rrf-expansion",
        "label": "RRF fusion + expansion",
        "chunking": "clause-aware",
        "strategy": "dense + lexical, RRF k=60",
        "expansion": True,
    },
}


def _services(request: Request) -> Any:
    services = request.app.state.services
    if services.retrieval is None:
        raise HTTPException(
            status_code=503,
            detail=services.embedder_error or "no embedding provider is configured",
        )
    return services


def _title(filename: str) -> str:
    return filename.removesuffix(".txt").removesuffix(".pdf").replace("-", " ")


_KINDS = (
    ("DISTRIBUT", "Distribution"),
    ("SUPPLY", "Supply"),
    ("MANUFACTUR", "Manufacturing"),
    ("TRANSPORTATION", "Transportation"),
    ("LOGISTICS", "Logistics"),
    ("RESELLER", "Reseller"),
    ("OUTSOURCING", "Outsourcing"),
    ("STRATEGIC", "Strategic alliance"),
    ("SERVICE", "Services"),
)


def _kind(document: Document) -> str:
    """Prefer what ingest recorded; fall back to the filename rather than to a shrug."""
    recorded = str(document.meta.get("kind", "")).strip()
    if recorded:
        return recorded
    upper = document.filename.upper()
    for needle, label in _KINDS:
        if needle in upper:
            return label
    return "Agreement"


def _citation(chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "chunkId": str(chunk.chunk_id),
        "text": chunk.text,
        "span": {"start": chunk.char_start, "end": chunk.char_end},
        "score": round(chunk.score, 6),
        "page": chunk.page,
        "clauseId": chunk.clause_id,
        "clauseTitle": chunk.clause_title,
    }


def _evidence(run_id: str) -> dict[str, Any] | None:
    """Read an arm's corpus metrics from the committed evaluation artifact."""
    import json

    from ...paths import EVAL_RESULTS_DIR

    path = EVAL_RESULTS_DIR / f"{run_id}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "ok":
        return None
    metrics = payload["metrics"]
    return {
        "runId": run_id,
        "recallAt6": metrics["recall@6"],
        "mrr": metrics["mrr"],
        "ndcgAt10": metrics["ndcg@10"],
        "latencyMsP50": metrics["latency_ms_p50"],
        "embedMsP50": metrics["embed_ms_p50"],
        "searchMsP50": metrics["search_ms_p50"],
        "questions": metrics["n_evaluated"],
        "datasetSha256": payload["dataset"]["sha256"][:16],
        "embeddingProvider": payload["environment"]["embedding"]["provider"],
    }


@router.get("/documents")
def list_documents() -> dict[str, Any]:
    with session_scope() as session:
        rows = session.execute(
            select(
                Document,
                func.count(Chunk.id).label("chunk_count"),
                func.count(Chunk.clause_id).label("clause_count"),
            )
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .group_by(Document.id)
            .order_by(Document.filename)
        ).all()
        return {
            "source": "http",
            "contracts": [
                {
                    "id": str(row[0].id),
                    "title": _title(row[0].filename),
                    "party": _title(row[0].filename).split(" ")[0] or "Unknown",
                    "kind": _kind(row[0]),
                    "pageCount": max(1, row[0].page_count),
                    "charCount": max(1, row[0].char_count),
                    "clauseCount": int(row.clause_count),
                    "chunkCount": int(row.chunk_count),
                }
                for row in rows
            ],
        }


@router.post("/documents", status_code=201)
async def upload_contract(request: Request, file: UploadFile) -> dict[str, Any]:
    """Accept a PDF, ingest it, and return it in the same shape the list uses.

    Ingestion runs inline in this request (there is no Redis worker in the default
    deployment). It is the same parse, clause-aware chunk, hash and embed path the
    evaluation and the seed script use, so an uploaded contract is indistinguishable from
    a seeded one the moment it returns. Re-uploading identical content is a no-op through
    the SHA-256 hash, and the response says so.
    """
    services = _services(request)
    settings = services.settings

    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"file exceeds the {settings.max_upload_bytes} byte limit"
        )
    if not payload.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="only PDF uploads are accepted")

    try:
        parsed = parse_pdf_bytes(
            payload, file.filename or "upload.pdf", max_pages=settings.max_pdf_pages
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with session_scope() as session:
        result = index_parsed_document(
            session,
            parsed,
            embedder=services.embedder,
            chunk_strategy=settings.chunk_strategy,
            index_name=settings.chunk_strategy,
            chunk_overlap=settings.chunk_overlap,
            clause_ceiling=settings.clause_chunk_ceiling,
            byte_size=len(payload),
        )
        document = session.get(Document, result.document_id)
        assert document is not None
        clause_count = session.execute(
            select(func.count(Chunk.clause_id)).where(Chunk.document_id == document.id)
        ).scalar_one()
        chunk_count = session.execute(
            select(func.count(Chunk.id)).where(Chunk.document_id == document.id)
        ).scalar_one()
        logger.info(
            "web_upload",
            document_id=str(document.id),
            chunks=result.chunk_count,
            deduplicated=result.deduplicated,
        )
        return {
            "source": "http",
            "deduplicated": result.deduplicated,
            "contract": {
                "id": str(document.id),
                "title": _title(document.filename),
                "party": _title(document.filename).split(" ")[0] or "Unknown",
                "kind": _kind(document),
                "pageCount": max(1, document.page_count),
                "charCount": max(1, document.char_count),
                "clauseCount": int(clause_count),
                "chunkCount": int(chunk_count),
            },
        }


@router.get("/documents/{document_id}/text")
def get_document_text(document_id: uuid.UUID, request: Request) -> dict[str, Any]:
    scope = getattr(request.app.state, "document_scope", None)
    if scope is not None:
        scope.require(request, str(document_id))
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document not found")
        chunks = session.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
        ).scalars()
        by_index: dict[str, list[dict[str, Any]]] = {}
        for chunk in chunks:
            by_index.setdefault(chunk.index_name, []).append(
                {
                    "id": str(chunk.id),
                    "ordinal": chunk.ordinal,
                    "page": chunk.page,
                    "start": chunk.char_start,
                    "end": chunk.char_end,
                    "clauseId": chunk.clause_id,
                    "clauseTitle": chunk.clause_title,
                }
            )
        return {
            "source": "http",
            "id": str(document.id),
            "title": _title(document.filename),
            "pageCount": max(1, document.page_count),
            "charCount": max(1, document.char_count),
            "fullText": document.full_text,
            "chunks": by_index,
        }


class AnalyseBody(BaseModel):
    contractId: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)


@router.post("/analyse")
def analyse(request: Request, body: AnalyseBody) -> dict[str, Any]:
    services = _services(request)
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    scope = getattr(request.app.state, "document_scope", None)
    if scope is not None:
        scope.require(request, str(body.contractId))

    config = RetrievalConfig.from_settings(services.settings)
    with session_scope() as session:
        chunks, trace = services.retrieval.search(
            session, body.query, config=config, document_id=body.contractId
        )

    answer = ""
    status = "unavailable"
    detail: str | None = None
    generation_ms = 0.0

    if services.generation.available:
        started = time.perf_counter()
        try:
            answer = "".join(
                services.generation.stream(SYSTEM_PROMPT, build_user_prompt(body.query, chunks))
            )
            status = "ok"
        except Exception as exc:
            status = "error"
            detail = f"{type(exc).__name__}: {exc}"
        generation_ms = (time.perf_counter() - started) * 1000
    elif chunks:
        # No generation provider. Rather than an empty record, read the most relevant
        # clauses back as continuous prose. The chips carry "where", so no "the passage
        # most responsive to..." scaffolding and no "page N also bears on this". An
        # extractive answer cannot hallucinate, which is why this is acceptable as a
        # fallback rather than a stopgap that invents text.
        def _trim(text: str) -> str:
            flat = " ".join(text.split())
            if len(flat) <= 360:
                return flat
            cut = flat[:360]
            stop = max(cut.rfind(". "), cut.rfind("; "))
            return (cut[: stop + 1] if stop > 140 else cut + "...").strip()

        parts: list[str] = []
        seen: set[str] = set()
        for chunk in chunks[:3]:
            text = _trim(chunk.text)
            key = text[:48].lower()
            if key in seen:
                continue
            seen.add(key)
            parts.append(text)
            if len(" ".join(parts)) > 620:
                break
        answer = " ".join(parts)
        status = "ok"
        detail = (
            "Answer taken directly from the contract. Use the sources below to jump to each clause."
        )
    else:
        detail = "Retrieval returned nothing for this query in this contract."

    usage = services.generation.usage()
    with session_scope() as session:
        session.add(
            Query(
                request_id=request_id,
                document_id=body.contractId,
                question=body.query,
                config_hash=config.hash,
                embed_ms=trace.embed_ms,
                retrieval_ms=trace.dense_ms + trace.lexical_ms + trace.fusion_ms,
                rerank_ms=trace.rerank_ms,
                generation_ms=generation_ms,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_usd=usage.cost_usd,
            )
        )

    logger.info("web_analyse", citations=len(chunks), strategy=config.strategy)
    return {
        "source": "http",
        "answer": answer,
        "answerStatus": status,
        "answerDetail": detail,
        "citations": [_citation(chunk) for chunk in chunks],
        "timing": {
            "embedMs": round(trace.embed_ms, 2),
            "retrieveMs": round(trace.dense_ms + trace.lexical_ms + trace.fusion_ms, 2),
            "generateMs": round(generation_ms, 2),
        },
    }


class CompareBody(BaseModel):
    contractId: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    configs: list[str] = Field(min_length=2)


@router.post("/compare")
def compare(request: Request, body: CompareBody) -> dict[str, Any]:
    """Run one query through two retrieval configurations against the same document.

    Distinct from `POST /compare`, which diffs the extracted fields of two documents. Two
    genuinely different comparisons; the prefix keeps them apart.
    """
    services = _services(request)
    scope = getattr(request.app.state, "document_scope", None)
    if scope is not None:
        scope.require(request, str(body.contractId))

    unknown = [name for name in body.configs if name not in ARM_CONFIGS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown configurations: {unknown}")

    base = RetrievalConfig.from_settings(services.settings)
    arms: list[dict[str, Any]] = []
    with session_scope() as session:
        for name in body.configs:
            spec = ARM_CONFIGS[name]
            config = RetrievalConfig(
                **(
                    base.to_dict()
                    | {
                        "strategy": "mmr" if name == "mmr" else "rrf",
                        "expansion": bool(spec["expansion"]),
                        "k": 6,
                        "index_name": "clause-aware",
                        "chunk_strategy": "clause-aware",
                    }
                )
            )
            chunks, trace = services.retrieval.search(
                session, body.query, config=config, document_id=body.contractId
            )
            evidence = _evidence(ARM_RUNS[name])
            if evidence is None:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"no committed evaluation artifact for {ARM_RUNS[name]}; "
                        "run python -m eval.run first"
                    ),
                )
            arms.append(
                {
                    "config": spec,
                    "chunks": [_citation(chunk) for chunk in chunks],
                    "evidence": evidence,
                    "timing": {
                        "embedMs": round(trace.embed_ms, 2),
                        "retrieveMs": round(trace.dense_ms + trace.lexical_ms + trace.fusion_ms, 2),
                        "generateMs": 0.0,
                    },
                }
            )

    id_sets = [{chunk["chunkId"] for chunk in arm["chunks"]} for arm in arms]
    overlap = sorted(set.intersection(*id_sets)) if id_sets else []
    return {
        "source": "http",
        "arms": arms,
        "overlapChunkIds": overlap,
        "reference": _evidence(REFERENCE_RUN),
    }


@router.get("/metrics/latency")
def latency(window: int = 200) -> dict[str, Any]:
    """Latency measured from this deployment's own answered queries.

    Unlike the mock, these are real observations from the `queries` table rather than the
    committed corpus aggregate. With no queries answered yet the response reports zero
    samples and the interface shows its empty state, which is the honest thing for it to do.
    """
    with session_scope() as session:
        rows = session.execute(
            text(
                """
                SELECT embed_ms, retrieval_ms, rerank_ms, generation_ms
                FROM queries ORDER BY created_at DESC LIMIT :window
                """
            ),
            {"window": window},
        ).all()

    def percentile(values: list[float], fraction: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
        return round(ordered[index], 2)

    embed = [float(row[0]) for row in rows]
    retrieval = [float(row[1]) + float(row[2]) for row in rows]
    generation = [float(row[3]) for row in rows]
    totals = [sum(float(value) for value in row) for row in rows]

    return {
        "source": "http",
        "window": window,
        "samples": len(rows),
        "totalP50Ms": percentile(totals, 0.5),
        "totalP95Ms": percentile(totals, 0.95),
        "buckets": [
            {
                "phase": "embed",
                "p50Ms": percentile(embed, 0.5),
                "p95Ms": percentile(embed, 0.95),
            },
            {
                "phase": "retrieve",
                "p50Ms": percentile(retrieval, 0.5),
                "p95Ms": percentile(retrieval, 0.95),
            },
            {
                "phase": "generate",
                "p50Ms": percentile(generation, 0.5),
                "p95Ms": percentile(generation, 0.95),
            },
        ],
        "runId": None,
        "note": (
            "Measured from this deployment's answered queries, not from the committed "
            "golden set. Generation is zero when no generation provider is configured."
        ),
    }
