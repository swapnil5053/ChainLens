"""The risk rule engine.

Rules live in `risk_rules.yaml`, not here. This file is only the evaluator for the small
expression language that file uses, and it is deliberately not `eval`: a rules file is the
kind of thing that gets edited by someone who is not reading the Python, so it should not
be able to execute arbitrary code.

Every flag carries the span of the first field it names that was actually extracted, so a
flag in the interface links to the sentence that caused it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .schema import ContractExtraction, RiskFlag, RiskReport

RULES_PATH = Path(__file__).with_name("risk_rules.yaml")

# Two jurisdiction strings count as the same place when one contains the other after
# stripping the boilerplate. "the State of New York" and "New York" are one place.
_NOISE = re.compile(
    r"\b(the|state|commonwealth|republic|courts?|of|in|located|federal|district)\b", re.IGNORECASE
)


def _normalise_place(value: Any) -> str:
    return " ".join(_NOISE.sub(" ", str(value)).split()).lower()


class RuleError(ValueError):
    pass


def _value(extraction: ContractExtraction, field: str) -> Any:
    entry = extraction.fields.get(field)
    return entry.value if entry else None


def evaluate(clause: Any, extraction: ContractExtraction) -> bool:
    if not isinstance(clause, dict) or len(clause) != 1:
        raise RuleError(f"a condition must be a single-key mapping, got {clause!r}")
    (operator, operand), = clause.items()

    if operator == "present":
        return operand in extraction.fields
    if operator == "absent":
        return operand not in extraction.fields
    if operator == "not":
        return not evaluate(operand, extraction)
    if operator == "all":
        return all(evaluate(item, extraction) for item in operand)
    if operator == "any":
        return any(evaluate(item, extraction) for item in operand)

    if operator in {"equals", "lt", "lte", "gt", "gte", "matches", "same_place"}:
        field, expected = operand
        actual = _value(extraction, field)
        if actual is None:
            return False
        if operator == "equals":
            return bool(actual == expected)
        if operator == "matches":
            return re.search(str(expected), str(actual), re.IGNORECASE) is not None
        if operator == "same_place":
            other = _value(extraction, expected)
            if other is None:
                return False
            left, right = _normalise_place(actual), _normalise_place(other)
            return bool(left and right and (left in right or right in left))
        try:
            left_number, right_number = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {
            "lt": left_number < right_number,
            "lte": left_number <= right_number,
            "gt": left_number > right_number,
            "gte": left_number >= right_number,
        }[operator]

    raise RuleError(f"unknown operator {operator!r} in the rules file")


def load_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    payload: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload


def assess(extraction: ContractExtraction, path: Path = RULES_PATH) -> RiskReport:
    payload = load_rules(path)
    flags: list[RiskFlag] = []
    for rule in payload["rules"]:
        if not evaluate(rule["when"], extraction):
            continue
        anchor = next(
            (extraction.fields[name] for name in rule.get("fields", []) if name in extraction.fields),
            None,
        )
        flags.append(
            RiskFlag(
                rule_id=rule["id"],
                severity=rule["severity"],
                title=rule["title"],
                detail=" ".join(str(rule["detail"]).split()),
                fields=list(rule.get("fields", [])),
                char_start=anchor.char_start if anchor else None,
                char_end=anchor.char_end if anchor else None,
                source_page=anchor.source_page if anchor else None,
            )
        )
    order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda flag: (order[flag.severity], flag.rule_id))
    return RiskReport(
        document_id=extraction.document_id,
        flags=flags,
        rules_evaluated=len(payload["rules"]),
        rules_version=int(payload.get("version", 1)),
    )
