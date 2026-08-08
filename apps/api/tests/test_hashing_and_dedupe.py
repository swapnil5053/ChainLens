"""Defect 5: identical uploads must not be re-embedded."""

from __future__ import annotations

from chainlens.ingest.hashing import sha256_bytes, sha256_text
from chainlens.ingest.parse import parse_text


def test_identical_text_hashes_identically() -> None:
    first = parse_text("Master supply agreement.\n\nClause one.", "a.txt")
    second = parse_text("Master supply agreement.\n\nClause one.", "b.txt")
    assert first.sha256 == second.sha256


def test_line_ending_normalisation_does_not_change_the_hash() -> None:
    unix = parse_text("one\n\ntwo", "a.txt")
    windows = parse_text("one\r\n\r\ntwo", "b.txt")
    assert unix.sha256 == windows.sha256
    assert unix.full_text == windows.full_text


def test_different_content_hashes_differently() -> None:
    assert sha256_bytes(b"a") != sha256_bytes(b"b")
    assert sha256_text("a") == sha256_bytes(b"a")
