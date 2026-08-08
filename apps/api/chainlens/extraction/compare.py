"""Field-level diff between two extractions."""

from __future__ import annotations

import re
from typing import Any

from .schema import FIELD_NAMES, CompareReport, ContractExtraction, DiffStatus, FieldDiff


def _comparable(value: Any) -> Any:
    """Normalise for equality without being clever about it.

    Lists compare as sorted sets, so a force majeure clause that lists the same events in a
    different order is the same. Strings compare case-insensitively with runs of whitespace
    collapsed, because contract text is full of line breaks that carry no meaning. Numbers
    compare as numbers. Nothing else is coerced: 30 days and "thirty days" are different
    until an extractor makes them the same, which is the extractor's job, not the diff's.
    """
    if isinstance(value, list):
        return tuple(sorted(_comparable(item) for item in value))
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip().lower()
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value


def compare(left: ContractExtraction, right: ContractExtraction) -> CompareReport:
    diffs: list[FieldDiff] = []
    for name in FIELD_NAMES:
        left_field = left.fields.get(name)
        right_field = right.fields.get(name)
        if left_field is None and right_field is None:
            continue
        status: DiffStatus
        if left_field is None:
            status = "missing_left"
        elif right_field is None:
            status = "missing_right"
        elif _comparable(left_field.value) == _comparable(right_field.value):
            status = "same"
        else:
            status = "differs"
        diffs.append(FieldDiff(field=name, status=status, left=left_field, right=right_field))
    return CompareReport(
        left_document_id=left.document_id,
        right_document_id=right.document_id,
        diffs=diffs,
    )
