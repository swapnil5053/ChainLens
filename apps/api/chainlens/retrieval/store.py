"""Postgres-backed search arms.

Both arms read the same ``chunks`` table. The dense arm uses pgvector cosine distance
over ``embeddings``; the lexical arm uses the generated ``search_vector`` column with
``ts_rank_cd``. Keeping lexical search inside Postgres is why there is no second search
service to operate.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from .types import RetrievedChunk

_SELECT = """
    c.id, c.document_id, d.filename, c.ordinal, c.text, c.page,
    c.char_start, c.char_end, c.page_char_start, c.page_char_end,
    c.page_spans, c.clause_id, c.clause_title
"""

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "and",
        "or",
        "not",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        "with",
        "as",
        "from",
        "it",
        "its",
        "if",
        "any",
        "does",
        "do",
        "did",
        "shall",
        "will",
        "under",
        "over",
        "about",
        "into",
        "per",
    ]
)


def _as_vector(value: Any) -> Any:
    """pgvector values come back as a literal string from raw SQL."""
    if isinstance(value, str):
        return np.fromstring(value.strip("[]"), sep=",", dtype=np.float32)
    return np.asarray(value, dtype=np.float32)


def _row_to_chunk(row: Any, score: float, arm: str, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=row.id,
        document_id=row.document_id,
        filename=row.filename,
        ordinal=row.ordinal,
        text=row.text,
        page=row.page,
        char_start=row.char_start,
        char_end=row.char_end,
        page_char_start=row.page_char_start,
        page_char_end=row.page_char_end,
        page_spans=list(row.page_spans or []),
        clause_id=row.clause_id,
        clause_title=row.clause_title,
        score=score,
        ranks={arm: rank},
        scores={arm: score},
    )


def to_tsquery_string(query: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9]+", query.lower())
        if len(token) > 1 and token not in _STOPWORDS
    ]
    return " | ".join(dict.fromkeys(tokens))


def dense_search(
    session: Session,
    vector: Sequence[float],
    *,
    index_name: str,
    provider: str,
    limit: int,
    document_id: uuid.UUID | None = None,
    with_vectors: bool = False,
) -> list[RetrievedChunk]:
    literal = "[" + ",".join(f"{value:.6f}" for value in vector) + "]"
    extra = ", e.vector AS vec" if with_vectors else ""
    sql = text(
        f"""
        SELECT {_SELECT}, 1 - (e.vector <=> CAST(:qvec AS vector)) AS score {extra}
        FROM chunks c
        JOIN embeddings e ON e.chunk_id = c.id
        JOIN documents d ON d.id = c.document_id
        WHERE c.index_name = :index_name
          AND e.provider = :provider
          AND (CAST(:document_id AS uuid) IS NULL OR c.document_id = CAST(:document_id AS uuid))
        ORDER BY e.vector <=> CAST(:qvec AS vector)
        LIMIT :limit
        """
    )
    rows = session.execute(
        sql,
        {
            "qvec": literal,
            "index_name": index_name,
            "provider": provider,
            "document_id": str(document_id) if document_id else None,
            "limit": limit,
        },
    ).all()
    results = [
        _row_to_chunk(row, float(row.score), "dense", rank)
        for rank, row in enumerate(rows, start=1)
    ]
    if with_vectors:
        for result, row in zip(results, rows, strict=True):
            result.vector = _as_vector(row.vec)
    return results


def lexical_search(
    session: Session,
    query: str,
    *,
    index_name: str,
    limit: int,
    document_id: uuid.UUID | None = None,
) -> list[RetrievedChunk]:
    tsquery = to_tsquery_string(query)
    if not tsquery:
        return []
    sql = text(
        f"""
        SELECT {_SELECT}, ts_rank_cd(c.search_vector, q, 32) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id,
             to_tsquery('english', :tsquery) q
        WHERE c.index_name = :index_name
          AND c.search_vector @@ q
          AND (CAST(:document_id AS uuid) IS NULL OR c.document_id = CAST(:document_id AS uuid))
        ORDER BY score DESC
        LIMIT :limit
        """
    )
    rows = session.execute(
        sql,
        {
            "tsquery": tsquery,
            "index_name": index_name,
            "document_id": str(document_id) if document_id else None,
            "limit": limit,
        },
    ).all()
    return [
        _row_to_chunk(row, float(row.score), "lexical", rank)
        for rank, row in enumerate(rows, start=1)
    ]
