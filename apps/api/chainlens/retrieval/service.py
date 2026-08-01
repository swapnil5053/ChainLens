"""The retrieval pipeline.

One query embedding, one search per configured arm. v1 called ``retriever.invoke``
twice per question, because a second assignment in the LCEL chain requested the same
documents under a different key and then never used them. That cannot happen here: the
arms are explicit and the trace records exactly what ran and how long it took.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..embeddings.base import EmbeddingProvider
from .expansion import expand_query
from .fusion import maximal_marginal_relevance, reciprocal_rank_fusion
from .rerank import Reranker, RerankerUnavailable
from .store import dense_search, lexical_search
from .types import RetrievalTrace, RetrievedChunk


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    strategy: str = "rrf"
    k: int = 6
    fetch_k: int = 30
    rrf_k: int = 60
    mmr_lambda: float = 0.5
    expansion: bool = True
    index_name: str = "clause-aware"
    chunk_strategy: str = "clause-aware"

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> RetrievalConfig:
        settings = settings or get_settings()
        return cls(
            strategy=settings.retrieval_strategy,
            k=settings.retrieval_k,
            fetch_k=settings.retrieval_fetch_k,
            rrf_k=settings.rrf_k,
            mmr_lambda=settings.mmr_lambda,
            expansion=settings.query_expansion,
            index_name=settings.chunk_strategy,
            chunk_strategy=settings.chunk_strategy,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:12]


class RetrievalService:
    def __init__(self, embedder: EmbeddingProvider, reranker: Reranker | None = None) -> None:
        self.embedder = embedder
        self.reranker = reranker

    def search(
        self,
        session: Session,
        query: str,
        *,
        config: RetrievalConfig,
        document_id: uuid.UUID | None = None,
    ) -> tuple[list[RetrievedChunk], RetrievalTrace]:
        trace = RetrievalTrace(
            strategy=config.strategy, k=config.k, fetch_k=config.fetch_k, expanded_query=None
        )
        effective = expand_query(query) if config.expansion else query
        if effective != query:
            trace.expanded_query = effective

        needs_dense = config.strategy in {"dense", "mmr", "rrf", "rrf_rerank"}
        needs_lexical = config.strategy in {"lexical", "rrf", "rrf_rerank"}
        depth = config.fetch_k if config.strategy != "dense" else max(config.k, config.fetch_k)

        dense_hits: list[RetrievedChunk] = []
        lexical_hits: list[RetrievedChunk] = []
        query_vector: list[float] = []

        if needs_dense:
            start = time.perf_counter()
            query_vector = self.embedder.embed_query(effective)
            trace.embed_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            dense_hits = dense_search(
                session,
                query_vector,
                index_name=config.index_name,
                provider=self.embedder.name,
                limit=depth,
                document_id=document_id,
                with_vectors=config.strategy == "mmr",
            )
            trace.dense_ms = (time.perf_counter() - start) * 1000

        if needs_lexical:
            start = time.perf_counter()
            lexical_hits = lexical_search(
                session,
                effective,
                index_name=config.index_name,
                limit=depth,
                document_id=document_id,
            )
            trace.lexical_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        if config.strategy == "dense":
            results = dense_hits[: config.k]
        elif config.strategy == "lexical":
            results = lexical_hits[: config.k]
        elif config.strategy == "mmr":
            results = maximal_marginal_relevance(
                query_vector, dense_hits, k=config.k, lambda_mult=config.mmr_lambda
            )
        else:
            results = reciprocal_rank_fusion(
                [dense_hits, lexical_hits], k=config.rrf_k, limit=config.fetch_k
            )
        trace.fusion_ms = (time.perf_counter() - start) * 1000

        if config.strategy == "rrf_rerank":
            trace.reranker_available = bool(self.reranker and self.reranker.available)
            if self.reranker is not None and self.reranker.available:
                start = time.perf_counter()
                try:
                    results = self.reranker.rerank(effective, results, k=config.k)
                except RerankerUnavailable:
                    results = results[: config.k]
                trace.rerank_ms = (time.perf_counter() - start) * 1000
            else:
                # Graceful degradation: fusion order, truncated. The trace records that
                # no rerank happened, so nothing downstream can claim one did.
                results = results[: config.k]

        return list(results[: config.k]), trace
