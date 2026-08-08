"""The embedding provider interface.

Everything downstream is provider-agnostic: ingestion, retrieval and the evaluation
harness only ever see ``EmbeddingProvider``. Swapping the provider is a configuration
change, which is what makes it possible to run the whole system with no API keys.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence


class EmbeddingError(RuntimeError):
    """Raised when a provider cannot be constructed or cannot embed."""


class EmbeddingProvider(abc.ABC):
    #: Stable identifier written into every embedding row and every eval result.
    name: str = "unset"

    @property
    @abc.abstractmethod
    def dim(self) -> int: ...

    @abc.abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    @abc.abstractmethod
    def embed_query(self, text: str) -> list[float]: ...

    def describe(self) -> dict[str, object]:
        return {"provider": self.name, "dim": self.dim}
