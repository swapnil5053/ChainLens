"""Application dependencies, constructed once at startup."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings, get_settings
from ..embeddings.base import EmbeddingError, EmbeddingProvider
from ..embeddings.registry import build_provider
from ..generation.provider import GeminiGeneration, GenerationProvider, UnavailableGeneration
from ..logging import get_logger
from ..retrieval.rerank import CrossEncoderReranker, Reranker
from ..retrieval.service import RetrievalService

logger = get_logger(__name__)


@dataclass(slots=True)
class Services:
    settings: Settings
    embedder: EmbeddingProvider | None
    embedder_error: str | None
    reranker: Reranker
    generation: GenerationProvider
    retrieval: RetrievalService | None


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or get_settings()

    embedder: EmbeddingProvider | None = None
    embedder_error: str | None = None
    try:
        embedder = build_provider(settings)
    except EmbeddingError as exc:
        embedder_error = str(exc)
        logger.warning("embedding_provider_unavailable", error=str(exc))

    reranker = CrossEncoderReranker(settings.reranker_model)

    generation: GenerationProvider
    if settings.google_api_key:
        generation = GeminiGeneration(
            settings.google_api_key,
            model=settings.generation_model,
            temperature=settings.generation_temperature,
            timeout_seconds=settings.generation_timeout_seconds,
        )
    else:
        generation = UnavailableGeneration(
            "no generation provider configured: set CHAINLENS_GOOGLE_API_KEY. "
            "Retrieval and citations work without it."
        )

    return Services(
        settings=settings,
        embedder=embedder,
        embedder_error=embedder_error,
        reranker=reranker,
        generation=generation,
        retrieval=RetrievalService(embedder, reranker) if embedder else None,
    )
