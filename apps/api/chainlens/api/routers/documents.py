from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ...db.models import Chunk, Document, Embedding, Job
from ...db.session import session_scope
from ...ingest.parse import parse_pdf_bytes
from ...ingest.pipeline import index_parsed_document
from ...logging import get_logger
from ..schemas import DocumentSummary, JobResponse

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


def _summaries(session: Session) -> list[DocumentSummary]:
    rows = session.execute(
        select(
            Document,
            func.count(Chunk.id).label("chunk_count"),
            func.count(Chunk.clause_id).label("clause_count"),
            func.min(Chunk.chunk_strategy).label("chunk_strategy"),
        )
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    ).all()
    providers: dict[uuid.UUID, str] = {
        row[0]: row[1]
        for row in session.execute(
            select(Chunk.document_id, func.min(Embedding.provider))
            .join(Embedding, Embedding.chunk_id == Chunk.id)
            .group_by(Chunk.document_id)
        ).all()
    }
    return [
        DocumentSummary(
            id=row[0].id,
            filename=row[0].filename,
            sha256=row[0].sha256,
            status=row[0].status,
            page_count=row[0].page_count,
            char_count=row[0].char_count,
            chunk_count=int(row.chunk_count),
            clause_count=int(row.clause_count),
            chunk_strategy=row.chunk_strategy,
            embedding_provider=providers.get(row[0].id),
            created_at=row[0].created_at.isoformat() if row[0].created_at else "",
        )
        for row in rows
    ]


@router.get("", response_model=list[DocumentSummary])
def list_documents() -> list[DocumentSummary]:
    with session_scope() as session:
        return _summaries(session)


@router.get("/stats")
def corpus_stats() -> dict[str, int]:
    with session_scope() as session:
        row = session.execute(
            text(
                """
                SELECT (SELECT count(*) FROM documents)                 AS documents,
                       (SELECT count(*) FROM chunks)                    AS chunks,
                       (SELECT count(*) FROM embeddings)                AS embeddings,
                       (SELECT count(DISTINCT index_name) FROM chunks)  AS indexes
                """
            )
        ).one()
        return {
            "documents": int(row.documents),
            "chunks": int(row.chunks),
            "embeddings": int(row.embeddings),
            "indexes": int(row.indexes),
        }


@router.post("", response_model=JobResponse, status_code=202)
async def upload_document(request: Request, file: UploadFile) -> JobResponse:
    services = request.app.state.services
    settings = services.settings
    if services.embedder is None:
        raise HTTPException(
            status_code=503,
            detail=services.embedder_error or "no embedding provider is configured",
        )

    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"file exceeds the {settings.max_upload_bytes} byte limit"
        )
    if not payload.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="only PDF uploads are accepted")

    with session_scope() as session:
        job = Job(kind="ingest", state="queued", detail="accepted")
        session.add(job)
        session.flush()
        job_id = job.id

    try:
        parsed = parse_pdf_bytes(
            payload, file.filename or "upload.pdf", max_pages=settings.max_pdf_pages
        )
    except ValueError as exc:
        with session_scope() as session:
            row = session.get(Job, job_id)
            if row is not None:
                row.state, row.error = "failed", str(exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with session_scope() as session:
        row = session.get(Job, job_id)
        assert row is not None

        def progress(state: str, fraction: float, detail: str) -> None:
            row.state, row.progress, row.detail = state, fraction, detail
            session.flush()

        try:
            result = index_parsed_document(
                session,
                parsed,
                embedder=services.embedder,
                chunk_strategy=settings.chunk_strategy,
                index_name=settings.chunk_strategy,
                chunk_overlap=settings.chunk_overlap,
                clause_ceiling=settings.clause_chunk_ceiling,
                byte_size=len(payload),
                on_progress=progress,
            )
        except Exception as exc:  # pragma: no cover - defensive
            row.state, row.error = "failed", f"{type(exc).__name__}: {exc}"
            raise HTTPException(status_code=500, detail=row.error) from exc

        row.document_id = result.document_id
        row.timings_ms = dict(result.timings_ms)
        row.detail = (
            "identical content already indexed"
            if result.deduplicated
            else f"{result.chunk_count} chunks indexed"
        )
        logger.info(
            "ingest_complete",
            document_id=str(result.document_id),
            chunks=result.chunk_count,
            deduplicated=result.deduplicated,
        )
        return JobResponse(
            job_id=row.id,
            document_id=row.document_id,
            state=row.state,
            progress=row.progress,
            detail=row.detail,
            error=row.error,
            timings_ms=row.timings_ms,
        )


@router.get("/{document_id}")
def get_document(document_id: uuid.UUID) -> dict[str, object]:
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document not found")
        return {
            "id": str(document.id),
            "filename": document.filename,
            "sha256": document.sha256,
            "status": document.status,
            "page_count": document.page_count,
            "char_count": document.char_count,
            "pages": document.pages,
            "meta": document.meta,
        }


@router.get("/{document_id}/text")
def get_document_text(document_id: uuid.UUID) -> dict[str, object]:
    """Full text plus page boundaries, so the reader pane can mark exact spans."""
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document not found")
        return {
            "id": str(document.id),
            "filename": document.filename,
            "full_text": document.full_text,
            "pages": document.pages.get("pages", []),
        }


@router.get("/{document_id}/chunks")
def get_document_chunks(
    document_id: uuid.UUID, request: Request, limit: int | None = None
) -> list[dict[str, object]]:
    settings = request.app.state.services.settings
    cap = min(limit or settings.metadata_scan_limit, settings.metadata_scan_limit)
    with session_scope() as session:
        rows = session.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal).limit(cap)
        ).scalars()
        return [
            {
                "id": str(chunk.id),
                "ordinal": chunk.ordinal,
                "page": chunk.page,
                "clause_id": chunk.clause_id,
                "clause_title": chunk.clause_title,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "page_spans": chunk.page_spans,
                "token_estimate": chunk.token_estimate,
                "text": chunk.text,
            }
            for chunk in rows
        ]
