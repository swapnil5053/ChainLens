"""Retrieval result types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    ordinal: int
    text: str
    page: int
    char_start: int
    char_end: int
    page_char_start: int
    page_char_end: int
    page_spans: list[dict[str, int]]
    clause_id: str | None
    clause_title: str | None
    score: float
    #: Per-arm ranks, kept so fusion behaviour is inspectable in the UI and in evals.
    ranks: dict[str, int] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    #: Populated only when the caller needs vectors, currently MMR. Never serialised.
    vector: Any | None = None

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text) // 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "filename": self.filename,
            "ordinal": self.ordinal,
            "text": self.text,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "page_char_start": self.page_char_start,
            "page_char_end": self.page_char_end,
            "page_spans": self.page_spans,
            "clause_id": self.clause_id,
            "clause_title": self.clause_title,
            "score": self.score,
            "ranks": self.ranks,
            "scores": self.scores,
        }


@dataclass(slots=True)
class RetrievalTrace:
    strategy: str
    k: int
    fetch_k: int
    expanded_query: str | None
    embed_ms: float = 0.0
    dense_ms: float = 0.0
    lexical_ms: float = 0.0
    fusion_ms: float = 0.0
    rerank_ms: float = 0.0
    reranker_available: bool = False

    @property
    def total_ms(self) -> float:
        return self.embed_ms + self.dense_ms + self.lexical_ms + self.fusion_ms + self.rerank_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "k": self.k,
            "fetch_k": self.fetch_k,
            "expanded_query": self.expanded_query,
            "embed_ms": round(self.embed_ms, 3),
            "dense_ms": round(self.dense_ms, 3),
            "lexical_ms": round(self.lexical_ms, 3),
            "fusion_ms": round(self.fusion_ms, 3),
            "rerank_ms": round(self.rerank_ms, 3),
            "total_ms": round(self.total_ms, 3),
            "reranker_available": self.reranker_available,
        }
