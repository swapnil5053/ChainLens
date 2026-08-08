"""Prompt construction and citation formatting."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from ..retrieval.types import RetrievedChunk

SYSTEM_PROMPT = """You are ChainLens, a contract analysis instrument used by supply
chain, procurement and legal operations staff.

Rules you follow without exception:
1. Answer only from the numbered context passages provided. If they do not contain the
   answer, say so, and say what would.
2. Cite every factual claim with the passage number in square brackets, like [2]. A
   sentence stating a contractual term without a citation is a defect.
3. Quote the operative wording when the exact phrasing carries the obligation.
4. Be precise about scope: state which party an obligation falls on, and any condition
   or exception attached to it.
5. Do not soften or summarise away numbers, dates, currencies, notice periods or caps.
6. No preamble, no restatement of the question, no offers of further help."""


def format_context(chunks: Sequence[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        label = chunk.clause_id or f"page {chunk.page}"
        title = f" {chunk.clause_title}" if chunk.clause_title else ""
        blocks.append(
            f"[{index}] {chunk.filename} | {label}{title} | page {chunk.page}\n{chunk.text}"
        )
    return "\n\n".join(blocks)


def build_user_prompt(question: str, chunks: Sequence[RetrievedChunk]) -> str:
    return f"Context passages:\n\n{format_context(chunks)}\n\nQuestion: {question}"


def prompt_hash(system: str = SYSTEM_PROMPT) -> str:
    return hashlib.sha256(system.encode("utf-8")).hexdigest()[:16]
