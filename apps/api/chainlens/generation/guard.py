"""Groundedness guard.

A cheap, deterministic check that runs on every answer: each sentence stating a
contractual fact should carry a citation, and every citation should point at a passage
that was actually retrieved. This is not the LLM-judged groundedness metric in the
evaluation harness; it is the runtime guard that stops an uncited claim reaching the
interface unmarked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CITATION = re.compile(r"\[(\d{1,2})\]")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
# A sentence with none of these is usually a hedge or a transition, not a claim.
FACTUAL = re.compile(
    r"\b(shall|must|may|will|liab|cap|penal|terminat|notice|warrant|insur|deliver|"
    r"payment|days?|months?|years?|usd|eur|gbp)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class GroundednessReport:
    total_claims: int
    cited_claims: int
    uncited_sentences: list[str]
    invalid_citations: list[int]

    @property
    def ratio(self) -> float:
        return self.cited_claims / self.total_claims if self.total_claims else 1.0

    @property
    def passed(self) -> bool:
        return not self.invalid_citations and self.ratio >= 0.8

    def to_dict(self) -> dict[str, object]:
        return {
            "total_claims": self.total_claims,
            "cited_claims": self.cited_claims,
            "ratio": round(self.ratio, 3),
            "passed": self.passed,
            "uncited_sentences": self.uncited_sentences,
            "invalid_citations": self.invalid_citations,
        }


def check_groundedness(answer: str, passage_count: int) -> GroundednessReport:
    total = cited = 0
    uncited: list[str] = []
    invalid: list[int] = []
    for sentence in (part.strip() for part in SENTENCE.split(answer) if part.strip()):
        numbers = [int(match) for match in CITATION.findall(sentence)]
        invalid.extend(number for number in numbers if number < 1 or number > passage_count)
        if not FACTUAL.search(sentence):
            continue
        total += 1
        if numbers:
            cited += 1
        else:
            uncited.append(sentence)
    return GroundednessReport(
        total_claims=total,
        cited_claims=cited,
        uncited_sentences=uncited,
        invalid_citations=sorted(set(invalid)),
    )
