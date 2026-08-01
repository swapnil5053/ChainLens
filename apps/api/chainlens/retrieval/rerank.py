"""Cross-encoder reranking, with an explicit unavailable state.

The reranker is a hard dependency on model weights. When those weights cannot be
loaded the pipeline degrades to fusion-only and says so in the trace, rather than
pretending a rerank happened.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence

from .types import RetrievedChunk


class RerankerUnavailable(RuntimeError):
    pass


class Reranker(abc.ABC):
    name: str = "unset"

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def rerank(
        self, query: str, candidates: Sequence[RetrievedChunk], *, k: int
    ) -> list[RetrievedChunk]: ...


class CrossEncoderReranker(Reranker):
    """``BAAI/bge-reranker-base`` through sentence-transformers.

    Loading is lazy and failures are captured rather than raised at construction, so a
    deployment without the weights still serves answers from fusion alone.
    """

    def __init__(self, model: str = "BAAI/bge-reranker-base", device: str | None = None) -> None:
        self.name = model
        self._device = device
        self._model: object | None = None
        self._error: str | None = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.name, device=self._device)
        except Exception as exc:  # pragma: no cover - environment dependent
            self._error = f"{type(exc).__name__}: {exc}"
            self._model = None

    @property
    def available(self) -> bool:
        self._load()
        return self._model is not None

    @property
    def error(self) -> str | None:
        self._load()
        return self._error

    def rerank(
        self, query: str, candidates: Sequence[RetrievedChunk], *, k: int
    ) -> list[RetrievedChunk]:
        self._load()
        if self._model is None:
            raise RerankerUnavailable(self._error or "reranker weights not loaded")
        scores = self._model.predict([(query, hit.text) for hit in candidates])  # type: ignore[attr-defined]
        for hit, score in zip(candidates, scores, strict=True):
            hit.scores["rerank"] = float(score)
            hit.score = float(score)
        return sorted(candidates, key=lambda hit: hit.score, reverse=True)[:k]


class NullReranker(Reranker):
    """Explicitly does nothing, and admits it."""

    name = "none"

    def __init__(self, reason: str = "no reranker configured") -> None:
        self.reason = reason

    @property
    def available(self) -> bool:
        return False

    def rerank(
        self, query: str, candidates: Sequence[RetrievedChunk], *, k: int
    ) -> list[RetrievedChunk]:
        raise RerankerUnavailable(self.reason)
