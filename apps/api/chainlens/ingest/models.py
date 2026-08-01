"""Value objects for the ingestion pipeline.

The invariant everything downstream leans on: for every chunk,
``document.full_text[chunk.char_start:chunk.char_end] == chunk.text``, and the chunk's
page spans reconstruct the same string from page-local text. The citation mark in the
reader pane is a direct consequence of the second equality, so offsets are carried from
the parser rather than recomputed later.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Page:
    number: int
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    filename: str
    sha256: str
    full_text: str
    pages: tuple[Page, ...]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def page_for_offset(self, offset: int) -> Page:
        for page in self.pages:
            if page.char_start <= offset < page.char_end:
                return page
        return self.pages[-1]


@dataclass(frozen=True, slots=True)
class PageSpan:
    """A chunk's footprint on one page, in page-local character offsets."""

    page: int
    start: int
    end: int


@dataclass(slots=True)
class Chunk:
    ordinal: int
    text: str
    page: int
    char_start: int
    char_end: int
    page_char_start: int
    page_char_end: int
    page_spans: tuple[PageSpan, ...] = ()
    clause_id: str | None = None
    clause_title: str | None = None
    token_estimate: int = 0
    meta: dict[str, str] = field(default_factory=dict)
