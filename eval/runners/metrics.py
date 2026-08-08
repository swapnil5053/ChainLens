"""Retrieval metrics.

Relevance is derived mechanically from the CUAD answer spans: a chunk is relevant when
its character range overlaps an annotated answer span for that question. Nothing here is
judged by a model.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def relevance_flags(
    retrieved: Sequence[tuple[int, int]], gold: Sequence[tuple[int, int]]
) -> list[bool]:
    return [any(overlaps(span, gold_span) for gold_span in gold) for span in retrieved]


def recall_at_k(flags: Sequence[bool], relevant_total: int, k: int) -> float:
    """Share of all relevant chunks in the index that appear in the top k."""
    if relevant_total <= 0:
        return 0.0
    return sum(1 for flag in flags[:k] if flag) / relevant_total


def hit_at_k(flags: Sequence[bool], k: int) -> float:
    """1.0 when at least one relevant chunk is in the top k."""
    return 1.0 if any(flags[:k]) else 0.0


def reciprocal_rank(flags: Sequence[bool]) -> float:
    for index, flag in enumerate(flags, start=1):
        if flag:
            return 1.0 / index
    return 0.0


def ndcg_at_k(flags: Sequence[bool], relevant_total: int, k: int) -> float:
    gain = sum(
        (1.0 if flag else 0.0) / math.log2(index + 1)
        for index, flag in enumerate(flags[:k], start=1)
    )
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, min(relevant_total, k) + 1))
    return gain / ideal if ideal else 0.0


def span_coverage(
    retrieved: Sequence[tuple[int, int]], gold: Sequence[tuple[int, int]], k: int
) -> float:
    """Share of annotated answer characters the top k chunks actually contain.

    Recall counts chunks; this counts the text a reader would be shown. A retrieval that
    clips half a liability clause scores 1.0 on hit rate and lower here.
    """
    if not gold:
        return 0.0
    covered = total = 0
    for gold_start, gold_end in gold:
        total += gold_end - gold_start
        marks = [False] * (gold_end - gold_start)
        for span_start, span_end in retrieved[:k]:
            lower = max(span_start, gold_start) - gold_start
            upper = min(span_end, gold_end) - gold_start
            for offset in range(max(0, lower), max(0, upper)):
                marks[offset] = True
        covered += sum(marks)
    return covered / total if total else 0.0


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
