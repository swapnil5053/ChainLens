"""Phase 5 acceptance: extraction is span-grounded, rules are data, diffs are honest."""

from __future__ import annotations

import pytest

from chainlens.extraction.compare import compare
from chainlens.extraction.extractors import extract_document, verify_span
from chainlens.extraction.risk import RuleError, assess, evaluate, load_rules
from chainlens.extraction.schema import ContractExtraction, ExtractedField
from chainlens.ingest.parse import parse_text

CONTRACT = """MASTER SUPPLY AGREEMENT

1. DELIVERY

Supplier shall deliver the Products DDP the Buyer's nominated warehouse in accordance with
Incoterms 2020, within 48 hours of receipt of a purchase order.

2. LIQUIDATED DAMAGES

If Supplier fails to deliver on time, Supplier shall pay liquidated damages of USD 5,000
per day of delay, provided that such liquidated damages shall not exceed USD 100,000.

3. LIMITATION OF LIABILITY

The aggregate liability of either party under this Agreement shall not exceed USD 2,000,000.

4. TERM AND TERMINATION

This Agreement shall automatically renew for successive one year terms unless either party
gives ninety (90) days prior written notice of its intention to terminate.

5. WARRANTY

Supplier warrants the Products for a period of 24 months from delivery.

6. INSURANCE

Supplier shall at all times maintain product liability insurance of not less than
USD 5,000,000.

7. FORCE MAJEURE

Neither party shall be liable for any delay caused by an act of God, war, fire, flood,
earthquake, strike or embargo.

8. GOVERNING LAW

This Agreement is governed by the laws of the State of New York. The parties submit to the
exclusive jurisdiction of the courts of New York.

9. PAYMENT

Invoices are payable net 45 days from the date of invoice.
"""


@pytest.fixture()
def extraction() -> ContractExtraction:
    document = parse_text(CONTRACT, "master-supply.txt")
    return extract_document(document, document_id="test")


def test_every_emitted_field_slices_back_to_its_evidence(extraction: ContractExtraction) -> None:
    document = parse_text(CONTRACT, "master-supply.txt")
    assert extraction.fields, "nothing was extracted from a contract containing every field"
    for name, field in extraction.fields.items():
        sliced = document.full_text[field.char_start : field.char_end]
        assert sliced.strip(), f"{name} has an empty span"
        # `evidence` is the whitespace-collapsed form of the span, so compare that way.
        assert " ".join(sliced.split())[:400] == field.evidence


def test_the_commercially_important_fields_are_found(extraction: ContractExtraction) -> None:
    assert extraction.value("incoterm") == "DDP"
    assert extraction.value("delivery_sla_hours") == 48
    assert extraction.value("termination_notice_days") == 90
    assert extraction.value("auto_renew") is True
    assert extraction.value("warranty_period_months") == 24
    assert extraction.value("payment_terms_days") == 45
    assert extraction.value("insurance_required") is True
    assert "New York" in str(extraction.value("governing_law"))
    assert "act of god" in extraction.value("force_majeure_events")


def test_a_field_that_is_absent_is_listed_as_missing() -> None:
    document = parse_text("A short agreement with no commercial terms at all.\n", "bare.txt")
    result = extract_document(document, document_id="bare")
    assert result.fields == {}
    assert "liability_cap" in result.missing


def test_an_unlocatable_span_is_rejected_rather_than_emitted() -> None:
    document = parse_text(CONTRACT, "master-supply.txt")
    assert verify_span(document, 10, 20) is not None
    assert verify_span(document, -1, 20) is None
    assert verify_span(document, 5, 5) is None
    assert verify_span(document, 0, len(document.full_text) + 1) is None


def test_risk_rules_fire_and_carry_a_span(extraction: ContractExtraction) -> None:
    report = assess(extraction)
    assert report.rules_evaluated >= 8
    fired = {flag.rule_id for flag in report.flags}
    # This contract caps liability and gives 90 days notice, so neither should fire.
    assert "uncapped-liability" not in fired
    assert "auto-renew-short-notice" not in fired
    # It does not mention an epidemic, and that rule should fire.
    assert "force-majeure-no-epidemic" in fired
    for flag in report.flags:
        if flag.fields and any(name in extraction.fields for name in flag.fields):
            assert flag.char_start is not None and flag.source_page is not None


def test_short_notice_auto_renewal_is_flagged() -> None:
    document = parse_text(CONTRACT.replace("ninety (90) days", "ten (10) days"), "short-notice.txt")
    report = assess(extract_document(document, document_id="short"))
    assert "auto-renew-short-notice" in {flag.rule_id for flag in report.flags}


def test_rules_live_in_yaml_not_in_code() -> None:
    payload = load_rules()
    assert payload["version"] >= 1
    assert len(payload["rules"]) >= 8
    for rule in payload["rules"]:
        assert {"id", "severity", "title", "detail", "when"} <= set(rule)
        assert rule["severity"] in {"low", "medium", "high"}


def test_the_rule_language_rejects_an_unknown_operator() -> None:
    empty = ContractExtraction(document_id="x", filename="x.txt")
    with pytest.raises(RuleError):
        evaluate({"exec": "rm -rf /"}, empty)
    with pytest.raises(RuleError):
        evaluate({"present": "a", "absent": "b"}, empty)


def _field(name: str, value: object) -> ExtractedField:
    return ExtractedField(
        field=name,
        value=value,
        confidence=0.9,
        source_page=1,
        char_start=0,
        char_end=5,
        evidence="stub",
    )


def test_compare_marks_each_of_the_four_statuses() -> None:
    left = ContractExtraction(
        document_id="l",
        filename="l.txt",
        fields={
            "incoterm": _field("incoterm", "DDP"),
            "payment_terms_days": _field("payment_terms_days", 45),
            "governing_law": _field("governing_law", "State of New York"),
        },
    )
    right = ContractExtraction(
        document_id="r",
        filename="r.txt",
        fields={
            "incoterm": _field("incoterm", "FOB"),
            "payment_terms_days": _field("payment_terms_days", 45),
            "jurisdiction": _field("jurisdiction", "London"),
        },
    )
    report = compare(left, right)
    statuses = {diff.field: diff.status for diff in report.diffs}
    assert statuses["incoterm"] == "differs"
    assert statuses["payment_terms_days"] == "same"
    assert statuses["governing_law"] == "missing_right"
    assert statuses["jurisdiction"] == "missing_left"
    assert report.differing == 3


def test_compare_ignores_ordering_and_whitespace_but_not_meaning() -> None:
    left = ContractExtraction(
        document_id="l",
        filename="l.txt",
        fields={
            "force_majeure_events": _field("force_majeure_events", ["war", "fire"]),
            "governing_law": _field("governing_law", "State  of\nNew York"),
        },
    )
    right = ContractExtraction(
        document_id="r",
        filename="r.txt",
        fields={
            "force_majeure_events": _field("force_majeure_events", ["fire", "war"]),
            "governing_law": _field("governing_law", "state of new york"),
        },
    )
    statuses = {diff.field: diff.status for diff in compare(left, right).diffs}
    assert statuses["force_majeure_events"] == "same"
    assert statuses["governing_law"] == "same"
