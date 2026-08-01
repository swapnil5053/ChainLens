"""Runtime configuration.

Every tunable that was a literal buried in v1 lives here: the collection name, the
metadata scan limit, chunk sizes, retrieval depth, the generation timeout.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EmbeddingProviderName = Literal["lsa", "sentence-transformers", "gemini", "stub"]
RetrievalStrategy = Literal["dense", "mmr", "lexical", "rrf", "rrf_rerank"]
ChunkStrategy = Literal["recursive-512", "recursive-1024", "clause-aware"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAINLENS_", env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://postgres@localhost:5432/chainlens",
        description="SQLAlchemy DSN for Postgres 16 with the pgvector extension.",
    )
    redis_url: str = "redis://localhost:6379/0"
    collection: str = Field(
        default="chainlens_v2",
        description="Logical index name. v1 hardcoded the string 'langchain'.",
    )
    metadata_scan_limit: int = Field(
        default=5_000,
        description="Upper bound on rows pulled by metadata scans. v1 used a bare "
        "limit=10000 inline.",
    )

    embedding_provider: EmbeddingProviderName = "lsa"
    embedding_dim: int = 384
    embedding_batch_size: int = 100
    gemini_embedding_model: str = "models/gemini-embedding-001"
    sentence_transformer_model: str = "BAAI/bge-small-en-v1.5"

    chunk_strategy: ChunkStrategy = "clause-aware"
    chunk_size: int = 1024
    chunk_overlap: int = 128
    clause_chunk_ceiling: int = 2_000

    retrieval_strategy: RetrievalStrategy = "rrf"
    retrieval_k: int = 6
    retrieval_fetch_k: int = 30
    rrf_k: int = 60
    mmr_lambda: float = 0.5
    query_expansion: bool = True
    reranker_model: str = "BAAI/bge-reranker-base"

    generation_model: str = "gemini-2.5-flash"
    generation_temperature: float = 0.2
    generation_timeout_seconds: float = 30.0
    google_api_key: str | None = None

    # Hardening
    rate_limit_per_minute: int = 120
    rate_limit_expensive_per_minute: int = 20
    #: "key:doc-a,doc-b;key2:*". Empty means no scoping, which /readyz reports.
    document_scopes: str = ""
    generation_retry_attempts: int = 3
    generation_retry_max_seconds: float = 20.0

    max_upload_bytes: int = 25 * 1024 * 1024
    max_pdf_pages: int = 1_500
    log_level: str = "INFO"

    def parsed_document_scopes(self) -> dict[str, set[str]]:
        """Parse the scope string into a mapping, tolerating an empty setting."""
        scopes: dict[str, set[str]] = {}
        for entry in self.document_scopes.split(";"):
            if ":" not in entry:
                continue
            key, documents = entry.split(":", 1)
            values = {item.strip() for item in documents.split(",") if item.strip()}
            if key.strip() and values:
                scopes[key.strip()] = values
        return scopes


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
