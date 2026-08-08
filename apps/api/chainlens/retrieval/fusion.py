"""Reciprocal rank fusion and maximal marginal relevance."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import numpy as np

from .types import RetrievedChunk


def reciprocal_rank_fusion(
    arms: Sequence[Sequence[RetrievedChunk]], *, k: int = 60, limit: int | None = None
) -> list[RetrievedChunk]:
    """Fuse ranked lists by 1 / (k + rank).

    k = 60 is the Cormack et al. value and is fixed by the brief. It damps deep ranks,
    so a chunk must appear reasonably high in at least one arm to survive.
    """
    merged: dict[uuid.UUID, RetrievedChunk] = {}
    fused: dict[uuid.UUID, float] = {}
    for arm in arms:
        for rank, hit in enumerate(arm, start=1):
            existing = merged.get(hit.chunk_id)
            if existing is None:
                merged[hit.chunk_id] = hit
            else:
                existing.ranks.update(hit.ranks)
                existing.scores.update(hit.scores)
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(merged.values(), key=lambda hit: fused[hit.chunk_id], reverse=True)
    for hit in ordered:
        hit.score = fused[hit.chunk_id]
        hit.scores["rrf"] = fused[hit.chunk_id]
    return ordered[:limit] if limit else ordered


def maximal_marginal_relevance(
    query_vector: Sequence[float],
    candidates: Sequence[RetrievedChunk],
    *,
    k: int,
    lambda_mult: float = 0.5,
) -> list[RetrievedChunk]:
    """Greedy MMR over candidates that carry their own embedding vector."""
    if any(hit.vector is None for hit in candidates) or not candidates:
        return list(candidates[:k])
    matrix = np.vstack([np.asarray(hit.vector) for hit in candidates])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    query = np.asarray(query_vector, dtype=np.float32)
    query = query / (np.linalg.norm(query) or 1.0)
    relevance = matrix @ query

    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < k:
        if not selected:
            best = int(max(remaining, key=lambda index: relevance[index]))
        else:
            penalty = (matrix[remaining] @ matrix[selected].T).max(axis=1)
            objective = lambda_mult * relevance[remaining] - (1 - lambda_mult) * penalty
            best = remaining[int(np.argmax(objective))]
        selected.append(best)
        remaining.remove(best)
    return [candidates[index] for index in selected]
