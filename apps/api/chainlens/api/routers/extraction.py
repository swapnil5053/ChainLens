"""Structured extraction, risk assessment and contract comparison."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ...db.models import Chunk, Document
from ...db.session import session_scope
from ...extraction.compare import compare as compare_extractions
from ...extraction.extractors import extract_document
from ...extraction.risk import assess
from ...extraction.schema import CompareReport, ContractExtraction, RiskReport
from ...ingest.models import Page, ParsedDocument
from ...logging import get_logger

router = APIRouter(tags=["extraction"])
logger = get_logger(__name__)


def _rebuild(document: Document) -> ParsedDocument:
    """Reconstruct the parsed document from what was stored at ingest time.

    The offsets in `documents.pages` are the ones chunking used, so extraction spans land
    in the same coordinate system the citations do. Re-parsing here instead would risk two
    slightly different paginations for the same document.
    """
    pages = tuple(
        Page(
            number=int(entry["number"]),
            text=document.full_text[int(entry["char_start"]) : int(entry["char_end"])],
            char_start=int(entry["char_start"]),
            char_end=int(entry["char_end"]),
        )
        for entry in document.pages.get("pages", [])
    )
    if not pages:
        pages = (
            Page(number=1, text=document.full_text, char_start=0, char_end=len(document.full_text)),
        )
    return ParsedDocument(
        filename=document.filename,
        sha256=document.sha256,
        full_text=document.full_text,
        pages=pages,
    )


def _clause_lookup(document_id: uuid.UUID, session: object) -> object:
    rows = list(
        session.execute(  # type: ignore[attr-defined]
            select(Chunk.char_start, Chunk.char_end, Chunk.clause_id, Chunk.clause_title)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.char_start)
        ).all()
    )

    def lookup(offset: int) -> tuple[str | None, str | None]:
        for start, end, clause_id, clause_title in rows:
            if start <= offset < end:
                return clause_id, clause_title
        return None, None

    return lookup


def _extract(document_id: uuid.UUID) -> ContractExtraction:
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document not found")
        parsed = _rebuild(document)
        lookup = _clause_lookup(document_id, session)
        return extract_document(parsed, clause_lookup=lookup, document_id=str(document_id))  # type: ignore[arg-type]


@router.post("/documents/{document_id}/extract", response_model=ContractExtraction)
def extract(document_id: uuid.UUID) -> ContractExtraction:
    extraction = _extract(document_id)
    logger.info(
        "extract",
        document_id=str(document_id),
        fields=len(extraction.fields),
        missing=len(extraction.missing),
    )
    return extraction


@router.get("/documents/{document_id}/risk", response_model=RiskReport)
def risk(document_id: uuid.UUID) -> RiskReport:
    return assess(_extract(document_id))


class CompareDocumentsRequest(BaseModel):
    left_document_id: uuid.UUID
    right_document_id: uuid.UUID = Field(
        description="The second contract. Comparing a document with itself is rejected."
    )


@router.post("/compare", response_model=CompareReport)
def compare(body: CompareDocumentsRequest) -> CompareReport:
    if body.left_document_id == body.right_document_id:
        raise HTTPException(status_code=422, detail="the two documents must be different")
    return compare_extractions(_extract(body.left_document_id), _extract(body.right_document_id))
