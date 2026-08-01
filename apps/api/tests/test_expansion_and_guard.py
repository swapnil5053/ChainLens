"""Query expansion and the runtime groundedness guard."""

from __future__ import annotations

from chainlens.generation.guard import check_groundedness
from chainlens.retrieval.expansion import expand_query, load_glossary


def test_glossary_expands_a_logistics_abbreviation() -> None:
    expanded = expand_query("What are the DDP obligations?")
    assert "delivered duty paid" in expanded.lower()
    assert expanded.startswith("What are the DDP obligations?")


def test_expansion_does_not_fire_on_a_substring_of_another_word() -> None:
    # "po" must not match inside "portion".
    assert expand_query("what portion of the fee") == "what portion of the fee"


def test_expansion_is_a_no_op_when_nothing_matches() -> None:
    assert expand_query("hello there") == "hello there"


def test_glossary_is_data_not_code() -> None:
    glossary = load_glossary()
    assert "fob" in glossary and "incoterms" in glossary["fob"]


def test_guard_flags_an_uncited_factual_claim() -> None:
    report = check_groundedness(
        "The liability cap is USD 1,000,000 [1]. Termination requires 30 days notice.", 2
    )
    assert report.total_claims == 2
    assert report.cited_claims == 1
    assert not report.passed
    assert report.uncited_sentences


def test_guard_rejects_a_citation_pointing_past_the_retrieved_passages() -> None:
    report = check_groundedness("The cap is USD 1m [9].", 3)
    assert report.invalid_citations == [9]
    assert not report.passed


def test_guard_passes_a_fully_cited_answer() -> None:
    report = check_groundedness("The cap is USD 1,000,000 [1]. Notice is 30 days [2].", 2)
    assert report.passed and report.ratio == 1.0
