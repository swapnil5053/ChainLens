"""Network-backed providers: Gemini, and sentence-transformers weights from the hub.

Both implement the same interface as the local providers. Neither can run in the
environment this was built in -- no API key, and both hosts are blocked by the egress
proxy -- so both fail loudly on construction rather than degrading into something that
silently produces different numbers.

Gemini is called over plain HTTP with an explicit client-level timeout. That is
deliberate: v1 wrapped the call in ``thread.join(timeout=30)``, which returns to the
caller but leaves the request in flight and still consuming quota.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from .base import EmbeddingError, EmbeddingProvider

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiEmbeddings(EmbeddingProvider):
    name = "gemini-embedding-001"

    def __init__(
        self,
        api_key: str | None,
        model: str = "models/gemini-embedding-001",
        dim: int = 768,
        batch_size: int = 100,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise EmbeddingError(
                "GOOGLE_API_KEY is not set, so the Gemini embedding provider cannot be "
                "constructed. Set CHAINLENS_EMBEDDING_PROVIDER=lsa to run locally."
            )
        self._key = api_key
        self._model = model
        self._dim = dim
        self._batch = batch_size
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_seconds))

    @property
    def dim(self) -> int:
        return self._dim

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            f"{_GEMINI_BASE}/{path}", params={"key": self._key}, json=payload
        )
        response.raise_for_status()
        return dict(response.json())

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch):
            window = texts[start : start + self._batch]
            payload = {
                "requests": [
                    {
                        "model": self._model,
                        "content": {"parts": [{"text": text}]},
                        "taskType": "RETRIEVAL_DOCUMENT",
                    }
                    for text in window
                ]
            }
            body = self._post(f"{self._model}:batchEmbedContents", payload)
            vectors.extend(item["values"] for item in body["embeddings"])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        body = self._post(
            f"{self._model}:embedContent",
            {
                "model": self._model,
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_QUERY",
            },
        )
        return list(body["embedding"]["values"])


class SentenceTransformerEmbeddings(EmbeddingProvider):
    """``BAAI/bge-small-en-v1.5``, the provider the brief specifies as the default.

    Selecting it without access to the model hub raises with the underlying error
    instead of falling back, so a silent provider swap can never contaminate a result.
    """

    name = "bge-small-en-v1.5"

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", device: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise EmbeddingError(
                "sentence-transformers is not installed. Install it and re-run with "
                "CHAINLENS_EMBEDDING_PROVIDER=sentence-transformers."
            ) from exc
        try:
            self._model = SentenceTransformer(model, device=device)
        except Exception as exc:  # pragma: no cover - environment dependent
            raise EmbeddingError(
                f"could not load {model}: {exc}. In the build environment for this "
                "repository every huggingface.co host was blocked by the egress proxy."
            ) from exc
        self._dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return [list(map(float, vector)) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(
            [f"Represent this sentence for searching relevant passages: {text}"],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return [float(value) for value in vector]
