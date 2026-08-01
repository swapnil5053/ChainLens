"""Phase 2 acceptance.

Character offsets are the load-bearing part of the citation feature, so they get the
strictest test in the suite: every chunk must be reproducible by slicing the stored
document text, and by slicing the stored page text using the recorded page spans. If
either equality fails, the reader pane would mark the wrong characters.
"""

from __future__ import annotations

import pytest

from chainlens.ingest.chunk import chunk_document, detect_headings
from chainlens.ingest.parse import PAGE_SEPARATOR, parse_text

STRATEGIES = ("recursive-512", "recursive-1024", "clause-aware")


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_chunk_offsets_reproduce_the_chunk_from_document_text(
    sample_contract: str, strategy: str
) -> None:
    document = parse_text(sample_contract, "contract.txt")
    chunks = chunk_document(document, strategy)
    assert chunks, "chunking produced nothing"
    for chunk in chunks:
        assert document.full_text[chunk.char_start : chunk.char_end] == chunk.text


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_page_spans_reproduce_the_chunk_from_page_text(sample_contract: str, strategy: str) -> None:
    document = parse_text(sample_contract, "contract.txt")
    for chunk in chunk_document(document, strategy):
        rebuilt = PAGE_SEPARATOR.join(
            document.pages[span.page - 1].text[span.start : span.end] for span in chunk.page_spans
        )
        assert rebuilt == chunk.text


def test_chunks_are_stripped_and_ordinals_are_contiguous(sample_contract: str) -> None:
    chunks = chunk_document(parse_text(sample_contract, "c.txt"), "clause-aware")
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.text == chunk.text.strip() for chunk in chunks)


def test_clause_headings_are_detected_and_carried_onto_chunks() -> None:
    text = (
        "MASTER SUPPLY AGREEMENT\n\n"
        "1. DEFINITIONS\n\nIn this agreement the following terms apply.\n\n"
        "14.3 Force Majeure\n\nNeither party shall be liable for delay caused by "
        "events beyond its reasonable control.\n\n"
        "ARTICLE VII - INDEMNIFICATION\n\nThe Supplier shall indemnify the Buyer.\n\n"
        "Section 4(b) Payment Terms\n\nInvoices are payable net 30 days.\n"
    )
    document = parse_text(text, "synthetic.txt")
    headings = detect_headings(document.full_text)
    ids = {heading.clause_id for heading in headings}
    assert {"1", "14.3"} <= ids
    assert any(value.upper().startswith("ARTICLE") for value in ids)
    assert any(value.lower().startswith("section 4") for value in ids)

    chunks = chunk_document(document, "clause-aware")
    force_majeure = [chunk for chunk in chunks if chunk.clause_id == "14.3"]
    assert force_majeure, "the force majeure clause did not become its own chunk"
    assert force_majeure[0].clause_title == "Force Majeure"
    assert "reasonable control" in force_majeure[0].text


def test_documents_without_headings_fall_back_to_recursive_chunking() -> None:
    document = parse_text("no headings here at all. " * 400, "flat.txt")
    chunks = chunk_document(document, "clause-aware")
    assert chunks
    assert all(chunk.clause_id is None for chunk in chunks)
