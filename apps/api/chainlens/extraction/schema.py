"""The structured extraction schema.

Every field carries where it came from, not just what it says. A value without a span is
not evidence, it is an assertion, and the whole point of this system is that a reader can
click through to the sentence. Fields whose span cannot be located in the document text
are dropped by the extractor rather than emitted with a null span.

Confidence is a documented heuristic, not a calibrated probability. It reflects how
specific the pattern that matched was and whether an anchor term was nearby; it must not
be read as "90 percent likely to be correct". The measured accuracy of these extractors is
in `eval/results/extraction__cuad.json`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

FieldName = Literal[
    "incoterm",
    "delivery_sla_hours",
    "penalty_per_day",
    "penalty_cap",
    "liability_cap",
    "termination_notice_days",
    "auto_renew",
    "force_majeure_events",
    "governing_law",
    "jurisdiction",
    "payment_terms_days",
    "warranty_period_months",
    "insurance_required",
]

FIELD_NAMES: tuple[str, ...] = (
    "incoterm",
    "delivery_sla_hours",
    "penalty_per_day",
    "penalty_cap",
    "liability_cap",
    "termination_notice_days",
    "auto_renew",
    "force_majeure_events",
    "governing_law",
    "jurisdiction",
    "payment_terms_days",
    "warranty_period_months",
    "insurance_required",
)

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class ExtractedField(BaseModel):
    """One extracted value, grounded in a character span of the source document."""

    field: str
    value: Any
    confidence: Confidence
    source_page: int
    char_start: int
    char_end: int
    clause_id: str | None = None
    clause_title: str | None = None
    #: The exact substring the value was read from. Verified against the document text
    #: before the field is emitted, so it cannot drift from the offsets beside it.
    evidence: str

    def span(self) -> tuple[int, int]:
        return self.char_start, self.char_end


class ContractExtraction(BaseModel):
    document_id: str
    filename: str
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    #: Fields the extractor looked for and did not find, listed explicitly. An absent key
    #: and an absent value are different things, and a reviewer needs to see which.
    missing: list[str] = Field(default_factory=list)
    extractor: str = "deterministic-v1"
    elapsed_ms: float = 0.0

    def value(self, name: str) -> Any:
        entry = self.fields.get(name)
        return entry.value if entry else None


class RiskFlag(BaseModel):
    rule_id: str
    severity: Literal["low", "medium", "high"]
    title: str
    detail: str
    #: Every flag points at the field, and therefore the span, that triggered it.
    fields: list[str] = Field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None
    source_page: int | None = None


class RiskReport(BaseModel):
    document_id: str
    flags: list[RiskFlag] = Field(default_factory=list)
    rules_evaluated: int = 0
    rules_version: int = 1


DiffStatus = Literal["same", "differs", "missing_left", "missing_right"]


class FieldDiff(BaseModel):
    field: str
    status: DiffStatus
    left: ExtractedField | None = None
    right: ExtractedField | None = None


class CompareReport(BaseModel):
    left_document_id: str
    right_document_id: str
    diffs: list[FieldDiff] = Field(default_factory=list)

    @property
    def differing(self) -> int:
        return sum(1 for diff in self.diffs if diff.status != "same")
