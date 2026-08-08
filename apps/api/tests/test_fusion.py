"""Fusion and MMR behaviour, tested without a database."""

from __future__ import annotations

import uuid

import numpy as np

from chainlens.retrieval.fusion import maximal_marginal_relevance, reciprocal_rank_fusion
from chainlens.retrieval.types import RetrievedChunk


def make(name: str, arm: str, rank: int, vector: list[float] | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid5(uuid.NAMESPACE_OID, name),
        document_id=uuid.uuid5(uuid.NAMESPACE_OID, "doc"),
        filename="c.txt",
        ordinal=0,
        text=name,
        page=1,
        char_start=0,
        char_end=1,
        page_char_start=0,
        page_char_end=1,
        page_spans=[],
        clause_id=None,
        clause_title=None,
        score=1.0 / rank,
        ranks={arm: rank},
        scores={arm: 1.0 / rank},
        vector=np.asarray(vector, dtype=np.float32) if vector else None,
    )


def test_rrf_promotes_a_chunk_that_both_arms_agree_on() -> None:
    # Rank is list position, not the rank recorded on the chunk, so the fixtures are
    # ordered deliberately: "b" is near the top of both arms, "a" only of one.
    dense = [make("a", "dense", 1), make("b", "dense", 2), make("c", "dense", 3)]
    lexical = [make("b", "lexical", 1), make("c", "lexical", 2)]
    fused = reciprocal_rank_fusion([dense, lexical], k=60)
    assert fused[0].text == "b"
    assert [chunk.text for chunk in fused] == ["b", "c", "a"]


def test_rrf_merges_arm_ranks_onto_the_surviving_chunk() -> None:
    fused = reciprocal_rank_fusion([[make("a", "dense", 1)], [make("a", "lexical", 4)]], k=60)
    assert fused[0].ranks == {"dense": 1, "lexical": 4}
    assert "rrf" in fused[0].scores


def test_rrf_k_damps_deep_ranks() -> None:
    arm = [make(f"chunk-{index}", "dense", index) for index in range(1, 31)]
    fused = {chunk.text: chunk.score for chunk in reciprocal_rank_fusion([arm], k=60)}
    assert fused["chunk-1"] > fused["chunk-30"]
    # With k = 60 the spread between first and thirtieth is deliberately small: one
    # arm alone should not dominate the fusion.
    assert fused["chunk-1"] / fused["chunk-30"] < 1.5


def test_mmr_penalises_a_near_duplicate_of_an_already_selected_chunk() -> None:
    query = [1.0, 0.0]
    candidates = [
        make("first", "dense", 1, [1.0, 0.0]),
        make("duplicate", "dense", 2, [0.99, 0.14]),
        make("diverse", "dense", 3, [0.0, 1.0]),
    ]
    # At lambda 0.5 relevance and redundancy cancel exactly for a perfect duplicate,
    # so the penalty is exercised at a value where it can actually change the order.
    selected = maximal_marginal_relevance(query, candidates, k=2, lambda_mult=0.3)
    assert [chunk.text for chunk in selected] == ["first", "diverse"]


def test_mmr_without_vectors_degrades_to_plain_truncation() -> None:
    candidates = [make("a", "dense", 1), make("b", "dense", 2)]
    assert [c.text for c in maximal_marginal_relevance([1.0], candidates, k=1)] == ["a"]
