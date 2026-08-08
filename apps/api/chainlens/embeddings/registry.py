"""Provider construction from configuration."""

from __future__ import annotations

from pathlib import Path

from ..config import Settings, get_settings
from ..paths import ARTIFACT_DIR
from .base import EmbeddingError, EmbeddingProvider
from .lsa import LsaEmbeddings
from .remote import GeminiEmbeddings, SentenceTransformerEmbeddings
from .stub import StubEmbeddings

DEFAULT_LSA_ARTIFACT = ARTIFACT_DIR / "lsa-384.pkl"


def build_provider(
    settings: Settings | None = None, *, artifact: Path | None = None
) -> EmbeddingProvider:
    settings = settings or get_settings()
    choice = settings.embedding_provider
    if choice == "lsa":
        path = artifact or DEFAULT_LSA_ARTIFACT
        if path.exists():
            return LsaEmbeddings.load(path)
        raise EmbeddingError(
            f"no fitted LSA artifact at {path}. Run 'python -m eval.build_index' before serving."
        )
    if choice == "sentence-transformers":
        return SentenceTransformerEmbeddings(settings.sentence_transformer_model)
    if choice == "gemini":
        return GeminiEmbeddings(
            settings.google_api_key,
            model=settings.gemini_embedding_model,
            batch_size=settings.embedding_batch_size,
            timeout_seconds=settings.generation_timeout_seconds,
        )
    if choice == "stub":
        return StubEmbeddings(settings.embedding_dim)
    raise EmbeddingError(f"unknown embedding provider: {choice}")
