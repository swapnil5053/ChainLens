"""PDF and plain-text parsing that retains character offsets.

``pypdf`` is used directly rather than through a loader wrapper: the loader v1 used
returned page objects with no offset information, which makes character-accurate
citation impossible.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

from .hashing import sha256_bytes, sha256_file
from .models import Page, ParsedDocument

PAGE_SEPARATOR = "\n\n"


def _assemble(filename: str, sha256: str, page_texts: list[str]) -> ParsedDocument:
    pages: list[Page] = []
    cursor = 0
    parts: list[str] = []
    for index, raw in enumerate(page_texts, start=1):
        text = raw.replace("\r\n", "\n").replace("\r", "\n")
        start = cursor
        end = start + len(text)
        pages.append(Page(number=index, text=text, char_start=start, char_end=end))
        parts.append(text)
        cursor = end + len(PAGE_SEPARATOR)
    return ParsedDocument(
        filename=filename,
        sha256=sha256,
        full_text=PAGE_SEPARATOR.join(parts),
        pages=tuple(pages),
    )


def _read(reader: PdfReader, max_pages: int | None) -> list[str]:
    if max_pages is not None and len(reader.pages) > max_pages:
        raise ValueError(
            f"document has {len(reader.pages)} pages, above the configured limit of {max_pages}"
        )
    return [page.extract_text() or "" for page in reader.pages]


def parse_pdf(path: Path, *, max_pages: int | None = None) -> ParsedDocument:
    reader = PdfReader(str(path))
    return _assemble(path.name, sha256_file(path), _read(reader, max_pages))


def parse_pdf_bytes(data: bytes, filename: str, *, max_pages: int | None = None) -> ParsedDocument:
    reader = PdfReader(io.BytesIO(data))
    return _assemble(filename, sha256_bytes(data), _read(reader, max_pages))


def parse_text(text: str, filename: str, *, page_chars: int = 3_000) -> ParsedDocument:
    """Parse a plain-text contract, paginated on paragraph boundaries.

    Used by the evaluation corpus, where sources are distributed as text. Pagination is
    deterministic so offsets are stable across runs.
    """
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    page_texts: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in normalised.split("\n\n"):
        if current and size + len(paragraph) > page_chars:
            page_texts.append("\n\n".join(current))
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        page_texts.append("\n\n".join(current))
    return _assemble(filename, sha256_bytes(normalised.encode("utf-8")), page_texts or [""])
