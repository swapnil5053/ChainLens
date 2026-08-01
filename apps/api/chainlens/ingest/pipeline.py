"""Ingestion: parse, chunk, embed, index, with an explicit state machine.

States: queued, parsing, chunking, embedding, indexing, ready, failed. Progress is
reported by the pipeline rather than guessed by the caller, which is what lets the
Documents screen show something truthful.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Chunk as ChunkRow
from ..db.models import Document as DocumentRow
from ..db.models import Embedding as EmbeddingRow
from ..embeddings.base import EmbeddingProvider
from .chunk import chunk_document
from .models import ParsedDocument

STATES = ("queued", "parsing", "chunking", "embedding", "indexing", "ready", "failed")

ProgressHook = Callable[[str, float, str], None]


@dataclass(slots=True)
class IngestResult:
    document_id: uuid.UUID
    sha256: str
    deduplicated: bool
    chunk_count: int
    page_count: int
    clause_count: int
    timings_ms: dict[str, float] = field(default_factory=dict)


def _noop(state: str, progress: float, detail: str) -> None:  # noqa: ARG001
    """Default progress hook. Ignores its arguments by design."""
    return None


def find_by_hash(session: Session, sha256: str) -> DocumentRow | None:
    return session.execute(
        select(DocumentRow).where(DocumentRow.sha256 == sha256)
    ).scalar_one_or_none()


def index_parsed_document(
    session: Session,
    parsed: ParsedDocument,
    *,
    embedder: EmbeddingProvider,
    chunk_strategy: str = "clause-aware",
    index_name: str | None = None,
    chunk_overlap: int = 128,
    clause_ceiling: int = 2_000,
    byte_size: int = 0,
    meta: dict[str, Any] | None = None,
    on_progress: ProgressHook = _noop,
    batch_size: int = 256,
) -> IngestResult:
    index_name = index_name or chunk_strategy
    timings: dict[str, float] = {}

    on_progress("parsing", 0.05, f"{parsed.page_count} pages")
    existing = find_by_hash(session, parsed.sha256)
    if existing is not None:
        already = session.execute(
            select(ChunkRow.id).where(
                ChunkRow.document_id == existing.id, ChunkRow.index_name == index_name
            )
        ).first()
        if already is not None:
            on_progress("ready", 1.0, "identical content already indexed")
            return IngestResult(
                document_id=existing.id,
                sha256=parsed.sha256,
                deduplicated=True,
                chunk_count=0,
                page_count=existing.page_count,
                clause_count=0,
                timings_ms={"total": 0.0},
            )
        document = existing
    else:
        document = DocumentRow(
            filename=parsed.filename,
            sha256=parsed.sha256,
            byte_size=byte_size,
            page_count=parsed.page_count,
            char_count=len(parsed.full_text),
            status="parsing",
            full_text=parsed.full_text,
            pages={
                "pages": [
                    {
                        "number": page.number,
                        "char_start": page.char_start,
                        "char_end": page.char_end,
                    }
                    for page in parsed.pages
                ]
            },
            meta=meta or {},
        )
        session.add(document)
        session.flush()

    start = time.perf_counter()
    on_progress("chunking", 0.2, f"strategy {chunk_strategy}")
    chunks = chunk_document(parsed, chunk_strategy, overlap=chunk_overlap, ceiling=clause_ceiling)
    timings["chunking"] = (time.perf_counter() - start) * 1000

    rows = [
        ChunkRow(
            document_id=document.id,
            index_name=index_name,
            ordinal=chunk.ordinal,
            text=chunk.text,
            page=chunk.page,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            page_char_start=chunk.page_char_start,
            page_char_end=chunk.page_char_end,
            page_spans=[
                {"page": span.page, "start": span.start, "end": span.end}
                for span in chunk.page_spans
            ],
            clause_id=chunk.clause_id,
            clause_title=chunk.clause_title,
            token_estimate=chunk.token_estimate,
            chunk_strategy=chunk_strategy,
        )
        for chunk in chunks
    ]
    session.add_all(rows)
    session.flush()

    on_progress("embedding", 0.5, f"{len(rows)} chunks via {embedder.name}")
    start = time.perf_counter()
    texts = [row.text for row in rows]
    vectors: list[list[float]] = []
    for offset in range(0, len(texts), batch_size):
        vectors.extend(embedder.embed_documents(texts[offset : offset + batch_size]))
    timings["embedding"] = (time.perf_counter() - start) * 1000

    on_progress("indexing", 0.85, "writing vectors")
    start = time.perf_counter()
    session.add_all(
        [
            EmbeddingRow(chunk_id=row.id, provider=embedder.name, dim=embedder.dim, vector=vector)
            for row, vector in zip(rows, vectors, strict=True)
        ]
    )
    document.status = "ready"
    session.flush()
    timings["indexing"] = (time.perf_counter() - start) * 1000
    timings["total"] = sum(timings.values())

    on_progress("ready", 1.0, f"{len(rows)} chunks indexed")
    return IngestResult(
        document_id=document.id,
        sha256=parsed.sha256,
        deduplicated=False,
        chunk_count=len(rows),
        page_count=parsed.page_count,
        clause_count=sum(1 for chunk in chunks if chunk.clause_id),
        timings_ms=timings,
    )
