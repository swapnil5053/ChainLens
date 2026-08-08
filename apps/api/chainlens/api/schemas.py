"""Request and response models for the HTTP surface."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    postgres: bool
    redis: bool
    embedding_provider: str | None
    reranker: str
    generation: str
    detail: dict[str, str] = Field(default_factory=dict)


class JobResponse(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID | None
    state: str
    progress: float
    detail: str
    error: str | None = None
    timings_ms: dict[str, Any] = Field(default_factory=dict)


class DocumentSummary(BaseModel):
    id: uuid.UUID
    filename: str
    sha256: str
    status: str
    page_count: int
    char_count: int
    chunk_count: int
    clause_count: int
    chunk_strategy: str | None
    embedding_provider: str | None
    created_at: str


class PageSpanModel(BaseModel):
    page: int
    start: int
    end: int


class CitationModel(BaseModel):
    index: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int
    char_start: int
    char_end: int
    page_char_start: int
    page_char_end: int
    page_spans: list[PageSpanModel]
    clause_id: str | None
    clause_title: str | None
    score: float
    ranks: dict[str, int]
    text: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    document_id: uuid.UUID | None = None
    k: int | None = Field(default=None, ge=1, le=20)
    strategy: str | None = None


class QueryResponse(BaseModel):
    request_id: str
    question: str
    answer: str | None
    answer_status: str
    answer_detail: str | None = None
    citations: list[CitationModel]
    trace: dict[str, Any]
    groundedness: dict[str, Any] | None = None
    config_hash: str


class MetricsSummary(BaseModel):
    window: int
    queries: int
    retrieval_ms_p50: float
    retrieval_ms_p95: float
    generation_ms_p50: float
    generation_ms_p95: float
    cost_usd_total: float
    note: str
