"""Tests for the extractive answer builder.

These lock in the behaviours that were actually wrong in earlier versions: redaction
notices being quoted as if they were provisions, all-capitals liability clauses being
discarded as if they were stamps, and "A.M. Best" splitting an insurance requirement in
half.
"""

from __future__ import annotations

from chainlens.generation.extractive import sentences, summarise

REDACTION = (
    "16 [***] = CERTAIN CONFIDENTIAL INFORMATION CONTAINED IN THIS DOCUMENT, MARKED BY "
    "BRACKETS, HAS BEEN OMITTED BECAUSE THE INFORMATION (I) IS NOT MATERIAL AND (II) "
    "WOULD BE COMPETITIVELY HARMFUL IF PUBLICLY DISCLOSED."
)
INSURANCE = (
    "10.4.1 Each of Supplier and CUTANEA shall maintain and keep in force at its sole cost "
    "and expense throughout the Term of this Agreement, Commercial General Liability "
    "Insurance from carriers having an A.M. Best rating of A, including Product Recall, "
    "Bodily Injury and Property Damage Insurance."
)
LIABILITY = (
    "EXCEPT AS OTHERWISE EXPRESSLY SET FORTH IN THIS AGREEMENT, IN NO EVENT WILL EITHER "
    "PARTY BE LIABLE FOR ANY SPECIAL, INDIRECT, CONSEQUENTIAL, OR INCIDENTAL DAMAGES, "
    "INCLUDING LOST PROFITS, HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY."
)


def test_redaction_notice_never_appears_in_an_answer() -> None:
    answer = summarise("What insurance must the supplier carry?", [REDACTION + " " + INSURANCE])
    assert "CONFIDENTIAL INFORMATION" not in answer
    assert "COMPETITIVELY HARMFUL" not in answer
    assert "Insurance" in answer


def test_capitalised_liability_clause_is_kept() -> None:
    """All-capitals is how a contract makes a clause conspicuous, not how it marks junk."""
    answer = summarise("What is the cap on liability?", [LIABILITY])
    assert "LIABLE" in answer


def test_abbreviation_does_not_split_a_sentence() -> None:
    parts = sentences("carriers having an A.M. Best rating of A. The next sentence begins.")
    assert parts[0] == "carriers having an A.M. Best rating of A."
    assert len(parts) == 2


def test_enumerated_heading_starts_a_new_sentence() -> None:
    parts = sentences("...provided herein. 5.8 Debarment. Each party warrants compliance.")
    assert any(p.startswith("Each party warrants") for p in parts)


def test_repeated_text_is_not_quoted_twice() -> None:
    answer = summarise("What are the payment terms?", [INSURANCE, INSURANCE, INSURANCE])
    assert answer.count("Commercial General Liability") <= 1


def test_answer_is_bounded_and_whole_sentences() -> None:
    answer = summarise("insurance", [INSURANCE * 6], max_chars=400)
    assert len(answer) <= 420
    assert answer.endswith((".", "...")), answer[-40:]


def test_no_candidates_returns_empty_rather_than_noise() -> None:
    assert summarise("anything", [REDACTION]) == ""


def test_every_returned_sentence_appears_in_the_source() -> None:
    """The property that makes this safe: it can quote, but it cannot invent."""
    source = INSURANCE + " " + LIABILITY
    answer = summarise("liability insurance", [source])
    flat = " ".join(source.split())
    for sentence in answer.split(". "):
        stem = sentence.strip().rstrip(".")
        if len(stem) > 30:
            assert stem in flat
