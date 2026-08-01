"""Latent semantic indexing embeddings: fitted on the corpus, no network required.

A substitute for ``BAAI/bge-small-en-v1.5``, which could not be downloaded in the
environment this was built in. See ADR-0003. It is a real dense model -- TF-IDF over
word and character n-grams, reduced by truncated SVD and L2 normalised, so cosine
similarity is meaningful -- but it is not a modern sentence encoder and no result
produced with it should be read as one.
"""

from __future__ import annotations

import pickle
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import Normalizer

from .base import EmbeddingError, EmbeddingProvider


class LsaEmbeddings(EmbeddingProvider):
    name = "lsa-tfidf-svd-384"

    def __init__(self, dim: int = 384, random_state: int = 20240101) -> None:
        self._dim = dim
        self._random_state = random_state
        self._pipeline: Pipeline | None = None

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def is_fitted(self) -> bool:
        return self._pipeline is not None

    def _build(self) -> Pipeline:
        features = FeatureUnion(
            [
                (
                    "word",
                    TfidfVectorizer(
                        analyzer="word",
                        ngram_range=(1, 2),
                        min_df=2,
                        max_df=0.85,
                        sublinear_tf=True,
                        strip_accents="unicode",
                        lowercase=True,
                    ),
                ),
                (
                    "char",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        ngram_range=(3, 5),
                        min_df=3,
                        max_features=200_000,
                        sublinear_tf=True,
                        lowercase=True,
                    ),
                ),
            ]
        )
        return Pipeline(
            [
                ("features", features),
                ("svd", TruncatedSVD(n_components=self._dim, random_state=self._random_state)),
                ("normalise", Normalizer(copy=False)),
            ]
        )

    def fit(self, corpus: Sequence[str]) -> LsaEmbeddings:
        if len(corpus) <= self._dim:
            raise EmbeddingError(
                f"corpus of {len(corpus)} texts is too small to fit {self._dim} "
                "components; pass more chunks or lower the dimensionality"
            )
        self._pipeline = self._build()
        self._pipeline.fit(list(corpus))
        return self

    def _require(self) -> Pipeline:
        if self._pipeline is None:
            raise EmbeddingError(
                "LsaEmbeddings must be fitted on the corpus, or loaded from an "
                "artifact, before it can embed anything"
            )
        return self._pipeline

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        matrix: Any = self._require().transform(list(texts))
        return np.asarray(matrix, dtype=np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump({"dim": self._dim, "pipeline": self._require()}, handle)

    @classmethod
    def load(cls, path: Path) -> LsaEmbeddings:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        model = cls(dim=int(payload["dim"]))
        model._pipeline = payload["pipeline"]
        return model

    def describe(self) -> dict[str, object]:
        return {
            "provider": self.name,
            "dim": self._dim,
            "family": "tfidf+svd",
            "fitted_on": "corpus",
            "substitute_for": "BAAI/bge-small-en-v1.5",
            "reason": "huggingface.co unreachable in build environment (ADR-0003)",
        }
