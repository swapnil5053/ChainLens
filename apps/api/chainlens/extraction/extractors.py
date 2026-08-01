"""Deterministic, span-grounded field extraction.

Why patterns rather than a model. The brief asks for schema-constrained extraction with
every value carrying its span, and for that extraction to be measured. A language model
was not available in this environment, and a model whose output cannot be checked against
the source is exactly the failure this project exists to avoid. Regular expressions over
contract language are crude, they will miss unusual phrasing, and their measured
precision and recall are in `eval/results/extraction__cuad.json` rather than asserted here.
What they are is verifiable: every value is read out of a located span, and a value whose
span cannot be found in the document is dropped rather than emitted.

The model-backed extractor slots in behind the same interface. Its output would go through
`verify_span` identically, which is the part that matters.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..ingest.models import ParsedDocument
from .schema import ContractExtraction, ExtractedField

# Confidence is a heuristic about pattern specificity, documented in schema.py.
HIGH, MEDIUM, LOW = 0.9, 0.7, 0.5

MONEY = r"(?:US\$|\$|USD|EUR|GBP|EUR|€|£)\s?[\d,]+(?:\.\d{2})?(?:\s?(?:million|billion|thousand))?"
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "forty-five": 45,
    "sixty": 60,
    "ninety": 90,
    "one hundred eighty": 180,
    "one hundred twenty": 120,
}

INCOTERMS = ("EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP")


@dataclass(frozen=True, slots=True)
class Candidate:
    value: object
    start: int
    end: int
    confidence: float


Extractor = Callable[[str], Iterable[Candidate]]
_REGISTRY: dict[str, Extractor] = {}


def extractor(name: str) -> Callable[[Extractor], Extractor]:
    def register(function: Extractor) -> Extractor:
        _REGISTRY[name] = function
        return function

    return register


def _to_int(raw: str) -> int | None:
    cleaned = raw.strip().lower().replace(",", "")
    if cleaned.isdigit():
        return int(cleaned)
    return NUMBER_WORDS.get(cleaned)


def _window(text: str, start: int, radius: int = 260) -> str:
    return text[max(0, start - radius) : start + radius].lower()


@extractor("incoterm")
def incoterm(text: str) -> Iterable[Candidate]:
    pattern = re.compile(rf"\b({'|'.join(INCOTERMS)})\b(?:\s*\(?Incoterms[^)]*\)?)?")
    for match in pattern.finditer(text):
        near = _window(text, match.start(), 160)
        # The three-letter codes collide with ordinary words in capitalised headings, so an
        # anchor term is required rather than optional.
        anchored = any(
            term in near for term in ("incoterm", "deliver", "shipment", "freight", "carriage")
        )
        if not anchored:
            continue
        yield Candidate(match.group(1).upper(), match.start(), match.end(), HIGH)


@extractor("delivery_sla_hours")
def delivery_sla_hours(text: str) -> Iterable[Candidate]:
    pattern = re.compile(
        r"within\s+([\d,]+|[a-z\-]+)\s+(hours?|business\s+days?|days?)\b", re.IGNORECASE
    )
    for match in pattern.finditer(text):
        near = _window(text, match.start(), 200)
        if not any(term in near for term in ("deliver", "ship", "dispatch", "lead time")):
            continue
        amount = _to_int(match.group(1))
        if amount is None:
            continue
        unit = match.group(2).lower()
        hours = amount if "hour" in unit else amount * 24
        yield Candidate(hours, match.start(), match.end(), MEDIUM if "day" in unit else HIGH)


@extractor("penalty_per_day")
def penalty_per_day(text: str) -> Iterable[Candidate]:
    pattern = re.compile(
        rf"({MONEY}|[\d.]+\s?%)\s+(?:per|for\s+each|each)\s+(?:calendar\s+)?day", re.IGNORECASE
    )
    for match in pattern.finditer(text):
        near = _window(text, match.start())
        if not any(
            term in near
            for term in ("liquidated damages", "penalt", "late", "delay", "service credit")
        ):
            continue
        yield Candidate(match.group(1).strip(), match.start(), match.end(), HIGH)


@extractor("penalty_cap")
def penalty_cap(text: str) -> Iterable[Candidate]:
    pattern = re.compile(
        rf"(?:not\s+exceed|shall\s+be\s+capped\s+at|up\s+to\s+a\s+maximum\s+of)\s+({MONEY}|[\d.]+\s?%[^.]{{0,40}})",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        near = _window(text, match.start())
        if not any(term in near for term in ("liquidated damages", "penalt", "service credit")):
            continue
        yield Candidate(match.group(1).strip(), match.start(), match.end(), MEDIUM)


@extractor("liability_cap")
def liability_cap(text: str) -> Iterable[Candidate]:
    patterns = (
        re.compile(
            rf"(?:aggregate|total|maximum|entire)\s+liability[^.]{{0,160}}?(?:not\s+exceed|limited\s+to|shall\s+be)\s+({MONEY}|[^.]{{0,80}})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"liability[^.]{{0,80}}?shall\s+not\s+exceed\s+({MONEY}|[^.]{{0,80}})", re.IGNORECASE
        ),
    )
    for index, pattern in enumerate(patterns):
        for match in pattern.finditer(text):
            value = re.sub(r"\s+", " ", match.group(1)).strip().rstrip(",;")
            if not value:
                continue
            yield Candidate(value, match.start(), match.end(), HIGH if index == 0 else MEDIUM)

    # Exclusion clauses. "IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR CONSEQUENTIAL
    # DAMAGES" is a limitation of liability even though it names no figure, and it is what
    # most of these agreements actually contain. Emitting it as a qualitative value is
    # honest; the risk rule `liability-cap-language-only` then flags that it is not a number.
    exclusion = re.compile(
        r"(?:in\s+no\s+event\s+shall|neither\s+party\s+(?:shall|will)\s+(?:not\s+)?be\s+liable"
        r"|shall\s+not\s+be\s+liable)[^.]{0,200}",
        re.IGNORECASE,
    )
    for match in exclusion.finditer(text):
        body = re.sub(r"\s+", " ", match.group(0)).strip()
        if len(body) < 30:
            continue
        yield Candidate(f"excluded: {body[:160]}", match.start(), match.end(), LOW)


_UNIT_DAYS = {
    "day": 1,
    "days": 1,
    "week": 7,
    "weeks": 7,
    "month": 30,
    "months": 30,
    "year": 365,
    "years": 365,
}


@extractor("termination_notice_days")
def termination_notice_days(text: str) -> Iterable[Candidate]:
    """Notice required to terminate or to stop a renewal, normalised to days.

    Contracts write "six (6) months' prior written notice" far more often than a bare day
    count, and where both a word and a parenthetical numeral appear the numeral is the
    authoritative one, so it is preferred. Months are converted at 30 days and years at
    365: approximate, and stated here rather than hidden, because the risk rules compare
    this against a 30-day threshold where the approximation does not change the verdict.
    """
    pattern = re.compile(
        r"\b(?:([a-z\-]+)\s*)?\(?\s*(\d{1,4})\s*\)?\s*"
        r"(days?|weeks?|months?|years?)[\u2019']?\s*(?:prior\s+)?(?:written\s+)?notice"
        r"|\b([a-z\-]+)\s+(days?|weeks?|months?|years?)[\u2019']?\s*"
        r"(?:prior\s+)?(?:written\s+)?notice",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        near = _window(text, match.start(), 220)
        anchored = any(
            term in near
            for term in ("terminat", "cancel", "renew", "non-renew", "not to renew", "expir")
        )
        if not anchored:
            continue
        numeral, unit = (match.group(2), match.group(3))
        if numeral is None:
            amount, unit = _to_int(match.group(4) or ""), match.group(5)
        else:
            amount = int(numeral)
        if amount is None or unit is None:
            continue
        days = amount * _UNIT_DAYS[unit.lower()]
        if days <= 0 or days > 3650:
            continue
        # A renewal-notice sentence is the one the reviewer wants; prefer it when both a
        # renewal and a plain termination sentence are present.
        confidence = HIGH if "renew" in near else MEDIUM
        yield Candidate(days, match.start(), match.end(), confidence)


@extractor("auto_renew")
def auto_renew(text: str) -> Iterable[Candidate]:
    positive = re.compile(
        r"(automatically\s+(?:renew|extend)[a-z]*|shall\s+(?:be\s+)?automatically\s+renewed|"
        r"successive\s+(?:renewal\s+)?(?:one|two|three|\d+)?[\s-]*(?:year|month)\s+(?:terms?|periods?)|"
        r"renew\w*\s+for\s+successive)",
        re.IGNORECASE,
    )
    for match in positive.finditer(text):
        yield Candidate(True, match.start(), match.end(), HIGH)
    negative = re.compile(
        r"(shall\s+not\s+automatically\s+renew|no\s+automatic\s+renewal)", re.IGNORECASE
    )
    for match in negative.finditer(text):
        yield Candidate(False, match.start(), match.end(), HIGH)


FORCE_MAJEURE_TERMS = (
    "act of god",
    "acts of god",
    "war",
    "terrorism",
    "riot",
    "civil commotion",
    "fire",
    "flood",
    "earthquake",
    "hurricane",
    "storm",
    "epidemic",
    "pandemic",
    "quarantine",
    "strike",
    "lockout",
    "labor dispute",
    "labour dispute",
    "embargo",
    "government action",
    "governmental action",
    "act of government",
    "explosion",
    "sabotage",
    "insurrection",
)


@extractor("force_majeure_events")
def force_majeure_events(text: str) -> Iterable[Candidate]:
    anchor = re.compile(r"force\s+majeure|beyond\s+(?:its|their|the)\s+reasonable\s+control", re.I)
    for match in anchor.finditer(text):
        # The clause body, not the heading: read forward from the anchor.
        window_start = match.start()
        window_end = min(len(text), window_start + 1400)
        body = text[window_start:window_end]
        lowered = body.lower()
        found = [term for term in FORCE_MAJEURE_TERMS if term in lowered]
        if len(found) < 2:
            continue
        # Canonicalise plurals so "act of god" and "acts of god" are one event.
        canonical = sorted({term.replace("acts of", "act of") for term in found})
        last = max(lowered.rfind(term) + len(term) for term in found)
        yield Candidate(canonical, window_start, window_start + last, HIGH)


@extractor("governing_law")
def governing_law(text: str) -> Iterable[Candidate]:
    pattern = re.compile(
        r"govern(?:ed|ing)\s+(?:by|law)[^.]{0,120}?laws?\s+of\s+(?:the\s+)?"
        r"((?:State\s+of\s+|Commonwealth\s+of\s+|Republic\s+of\s+)?[A-Z][A-Za-z .\-]{2,40})",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .,;")
        if len(value) < 3:
            continue
        yield Candidate(value, match.start(), match.end(), HIGH)


@extractor("jurisdiction")
def jurisdiction(text: str) -> Iterable[Candidate]:
    pattern = re.compile(
        r"(?:exclusive\s+)?(?:jurisdiction|venue)[^.]{0,120}?"
        r"(?:courts?\s+of|located\s+in)\s+((?:the\s+)?[A-Z][A-Za-z .\-]{2,50})",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .,;")
        yield Candidate(value, match.start(), match.end(), MEDIUM)


@extractor("payment_terms_days")
def payment_terms_days(text: str) -> Iterable[Candidate]:
    patterns = (
        re.compile(r"net\s+([\d]{1,3})\b", re.IGNORECASE),
        re.compile(
            r"within\s+([\d,]+|[a-z\-]+)\s+days?\s+(?:of|from|after)\s+(?:the\s+)?"
            r"(?:date\s+of\s+)?(?:receipt\s+of\s+)?invoice",
            re.IGNORECASE,
        ),
    )
    for index, pattern in enumerate(patterns):
        for match in pattern.finditer(text):
            days = _to_int(match.group(1))
            if days is None or days > 365:
                continue
            near = _window(text, match.start(), 200)
            if index == 0 and not any(
                t in near for t in ("payment", "invoice", "payable", "terms")
            ):
                continue
            yield Candidate(days, match.start(), match.end(), HIGH)


@extractor("warranty_period_months")
def warranty_period_months(text: str) -> Iterable[Candidate]:
    patterns = (
        re.compile(
            r"(?:warrant\w*)[^.]{0,140}?(?:period\s+of\s+|for\s+)"
            r"(?:[a-z\-]+\s*)?\(?(\d{1,4}|[a-z\-]+)\)?\s+(months?|years?|days?)",
            re.IGNORECASE,
        ),
        # "within seven (7) days after receipt ... defective" is a warranty window too.
        re.compile(
            r"within\s+(?:[a-z\-]+\s*)?\(?(\d{1,4}|[a-z\-]+)\)?\s*(days?|months?|years?)"
            r"[^.]{0,120}?(?:defect|warrant|reject|non-?conform)",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(text):
            amount = _to_int(match.group(1))
            if amount is None:
                continue
            unit = match.group(2).lower()
            months = amount * 12 if "year" in unit else (amount if "month" in unit else amount / 30)
            if months <= 0 or months > 600:
                continue
            yield Candidate(round(months, 2), match.start(), match.end(), HIGH)


@extractor("insurance_required")
def insurance_required(text: str) -> Iterable[Candidate]:
    pattern = re.compile(
        r"(?:shall|will|must)\s+(?:at\s+all\s+times\s+)?(?:maintain|carry|procure|obtain)"
        r"[^.]{0,120}?insurance",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        yield Candidate(True, match.start(), match.end(), HIGH)


def verify_span(document: ParsedDocument, start: int, end: int) -> str | None:
    """Return the exact document substring, or None when the span is not usable.

    This is the gate every candidate passes through, whatever produced it. A value whose
    span does not resolve is dropped: the brief is explicit that a field with an
    unlocatable span should not be emitted at all.
    """
    if start < 0 or end > len(document.full_text) or end <= start:
        return None
    evidence = document.full_text[start:end]
    return evidence if evidence.strip() else None


def _locate(document: ParsedDocument, start: int) -> tuple[int, str | None, str | None]:
    page = document.page_for_offset(start)
    return page.number, None, None


def extract_document(
    document: ParsedDocument,
    *,
    clause_lookup: Callable[[int], tuple[str | None, str | None]] | None = None,
    document_id: str = "",
) -> ContractExtraction:
    """Run every registered extractor and keep the highest-confidence verified candidate."""
    started = time.perf_counter()
    text = document.full_text
    fields: dict[str, ExtractedField] = {}
    missing: list[str] = []

    for name, function in _REGISTRY.items():
        best: ExtractedField | None = None
        for candidate in function(text):
            evidence = verify_span(document, candidate.start, candidate.end)
            if evidence is None:
                continue
            page_number, _, _ = _locate(document, candidate.start)
            clause_id, clause_title = (
                clause_lookup(candidate.start) if clause_lookup else (None, None)
            )
            entry = ExtractedField(
                field=name,
                value=candidate.value,
                confidence=candidate.confidence,
                source_page=page_number,
                char_start=candidate.start,
                char_end=candidate.end,
                clause_id=clause_id,
                clause_title=clause_title,
                evidence=re.sub(r"\s+", " ", evidence).strip()[:400],
            )
            if best is None or entry.confidence > best.confidence:
                best = entry
        if best is None:
            missing.append(name)
        else:
            fields[name] = best

    return ContractExtraction(
        document_id=document_id or document.sha256[:12],
        filename=document.filename,
        fields=fields,
        missing=sorted(missing),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )


__all__ = ["FIELD_NAMES_IMPLEMENTED", "Candidate", "extract_document", "verify_span"]
FIELD_NAMES_IMPLEMENTED: tuple[str, ...] = tuple(_REGISTRY)
