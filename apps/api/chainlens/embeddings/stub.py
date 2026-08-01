"""Deterministic hashed embeddings.

Used only so that unit tests covering plumbing can run without fitting a model. It is
never a valid source of an evaluation number, and the evaluation runner refuses to
record metrics produced with it.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from .base import EmbeddingProvider


class StubEmbeddings(EmbeddingProvider):
    name = "stub-hashed"
    #: Read by the eval runner, which will not write metrics for a fake provider.
    is_fake = True

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _vector(self, text: str) -> list[float]:
        buckets = [0.0] * self._dim
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            buckets[int.from_bytes(digest[:4], "big") % self._dim] += 1.0
        norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
        return [value / norm for value in buckets]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
