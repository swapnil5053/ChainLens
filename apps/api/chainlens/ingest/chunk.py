"""Chunking strategies.

``recursive-N``   the conventional separator-descent splitter, reimplemented so that it
                  reports character offsets. Present because the ablation compares
                  against it honestly.

``clause-aware``  splits on detected clause headings, so a chunk is a clause, which is
                  the unit a contract reader cites. Segments over the ceiling fall back
                  to recursive splitting inside the clause, and documents with no
                  detectable headings fall back entirely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Chunk, PageSpan, ParsedDocument

_ROMAN = "IVXLCDM"

HEADING_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 14.3 Force Majeure   /   2.1.4 Delivery Windows
    re.compile(
        r"^[ \t]*(?P<id>\d{1,2}(?:\.\d{1,3}){0,4})[.)]?[ \t]+"
        r"(?P<title>[A-Z][A-Za-z0-9 ,;'/&()\-]{2,80})[ \t]*$",
        re.MULTILINE,
    ),
    # ARTICLE VII - INDEMNIFICATION
    re.compile(
        rf"^[ \t]*(?P<id>ARTICLE[ \t]+(?:[{_ROMAN}]+|\d+))"
        r"(?:[ \t]*[-\u2013:.][ \t]*(?P<title>[^\n]{2,80}))?[ \t]*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Section 4(b) Payment Terms
    re.compile(
        r"^[ \t]*(?P<id>Section[ \t]+\d{1,3}(?:\.\d{1,3})*(?:\([a-z]\))?)"
        r"(?:[ \t]*[-\u2013:.]?[ \t]*(?P<title>[^\n]{2,80}))?[ \t]*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # 7. TERMINATION
    re.compile(
        r"^[ \t]*(?P<id>\d{1,2})\.[ \t]+(?P<title>[A-Z][A-Z0-9 ,;'/&()\-]{3,80})[ \t]*$",
        re.MULTILINE,
    ),
)

_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ")


@dataclass(frozen=True, slots=True)
class Heading:
    start: int
    end: int
    clause_id: str
    clause_title: str | None


def detect_headings(text: str) -> list[Heading]:
    found: dict[int, Heading] = {}
    for pattern in HEADING_PATTERNS:
        for match in pattern.finditer(text):
            start = match.start()
            if start in found:
                continue
            title = match.groupdict().get("title")
            found[start] = Heading(
                start=start,
                end=match.end(),
                clause_id=" ".join(match.group("id").split()),
                clause_title=title.strip() if title else None,
            )
    return [found[key] for key in sorted(found)]


def _split_recursive(text: str, offset: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """Return (start, end) spans relative to the containing document."""
    if len(text) <= size:
        return [(offset, offset + len(text))] if text.strip() else []

    for separator in _SEPARATORS:
        if separator not in text:
            continue
        spans: list[tuple[int, int]] = []
        cursor = 0
        buffer_start = 0
        buffer_len = 0
        pieces = text.split(separator)
        for index, piece in enumerate(pieces):
            piece_len = len(piece) + (len(separator) if index < len(pieces) - 1 else 0)
            if buffer_len and buffer_len + piece_len > size:
                spans.append((offset + buffer_start, offset + cursor))
                # Rewind for the overlap, then move forward to the next whitespace so the
                # overlapping chunk does not begin in the middle of a word.
                back = max(buffer_start, cursor - overlap)
                while back < cursor and not text[back].isspace():
                    back += 1
                while back < cursor and text[back].isspace():
                    back += 1
                buffer_start = back
                buffer_len = cursor - back
            if not buffer_len:
                buffer_start = cursor
            buffer_len += piece_len
            cursor += piece_len
        if buffer_len:
            spans.append((offset + buffer_start, offset + cursor))
        merged = [(s, e) for s, e in spans if text[s - offset : e - offset].strip()]
        if all(e - s <= size * 2 for s, e in merged):
            return merged
        break

    # Last resort: fixed-width slicing. Snap each boundary forward to the next whitespace
    # so a chunk never begins or ends mid-word. Without this a citation can render as
    # "ndemnifying Party ...", which reads as a bug even though the offsets are correct.
    def snap(position: int, limit: int) -> int:
        if position <= 0 or position >= len(text):
            return max(0, min(position, len(text)))
        cursor = position
        while cursor < len(text) and cursor - position < limit and not text[cursor].isspace():
            cursor += 1
        return cursor

    spans: list[tuple[int, int]] = []
    stride = max(1, size - overlap)
    cursor = 0
    while cursor < len(text):
        start = snap(cursor, 60) if cursor else 0
        end = snap(min(start + size, len(text)), 60)
        if end <= start:
            break
        if text[start:end].strip():
            spans.append((offset + start, offset + end))
        cursor = start + stride
    return spans


def _finalise(
    document: ParsedDocument, spans: list[tuple[int, int, str | None, str | None]]
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for start, end, clause_id, clause_title in spans:
        text = document.full_text[start:end]
        stripped = text.strip()
        if not stripped:
            continue
        # Tighten onto the stripped text so the recorded offsets stay exact.
        tight_start = start + (len(text) - len(text.lstrip()))
        tight_end = tight_start + len(stripped)
        page_spans: list[PageSpan] = []
        for candidate in document.pages:
            overlap_start = max(tight_start, candidate.char_start)
            overlap_end = min(tight_end, candidate.char_end)
            if overlap_start < overlap_end:
                page_spans.append(
                    PageSpan(
                        page=candidate.number,
                        start=overlap_start - candidate.char_start,
                        end=overlap_end - candidate.char_start,
                    )
                )
        if not page_spans:
            fallback = document.page_for_offset(tight_start)
            page_spans = [PageSpan(page=fallback.number, start=0, end=0)]
        chunks.append(
            Chunk(
                ordinal=0,
                text=stripped,
                page=page_spans[0].page,
                char_start=tight_start,
                char_end=tight_end,
                page_char_start=page_spans[0].start,
                page_char_end=page_spans[0].end,
                page_spans=tuple(page_spans),
                clause_id=clause_id,
                clause_title=clause_title,
                token_estimate=max(1, len(stripped) // 4),
            )
        )
    for ordinal, chunk in enumerate(chunks):
        chunk.ordinal = ordinal
    return chunks


def chunk_recursive(document: ParsedDocument, *, size: int, overlap: int) -> list[Chunk]:
    spans = _split_recursive(document.full_text, 0, size, overlap)
    return _finalise(document, [(s, e, None, None) for s, e in spans])


def chunk_clause_aware(
    document: ParsedDocument, *, ceiling: int, overlap: int, min_headings: int = 3
) -> list[Chunk]:
    text = document.full_text
    headings = detect_headings(text)
    if len(headings) < min_headings:
        return chunk_recursive(document, size=ceiling // 2, overlap=overlap)

    boundaries: list[tuple[int, int, str | None, str | None]] = []
    if headings[0].start > 0:
        boundaries.append((0, headings[0].start, None, "Preamble"))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start if index + 1 < len(headings) else len(text)
        boundaries.append((heading.start, end, heading.clause_id, heading.clause_title))

    spans: list[tuple[int, int, str | None, str | None]] = []
    for start, end, clause_id, clause_title in boundaries:
        segment = text[start:end]
        if len(segment) <= ceiling:
            spans.append((start, end, clause_id, clause_title))
            continue
        for sub_start, sub_end in _split_recursive(segment, start, ceiling, overlap):
            spans.append((sub_start, sub_end, clause_id, clause_title))
    return _finalise(document, spans)


def chunk_document(document: ParsedDocument, strategy: str, **kwargs: int) -> list[Chunk]:
    if strategy == "clause-aware":
        return chunk_clause_aware(
            document,
            ceiling=int(kwargs.get("ceiling", 2_000)),
            overlap=int(kwargs.get("overlap", 128)),
        )
    if strategy.startswith("recursive-"):
        size = int(strategy.split("-", 1)[1])
        return chunk_recursive(document, size=size, overlap=int(kwargs.get("overlap", size // 8)))
    raise ValueError(f"unknown chunk strategy: {strategy}")
