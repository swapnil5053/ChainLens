"""Build the extraction label set from CUAD.

The brief asks for field-level precision and recall against a hand-labelled subset of at
least 15 documents. Rather than hand-label anything, this uses the labels that already
exist: CUAD's lawyer annotations cover seven of the thirteen schema fields directly, over
all 29 documents in the committed corpus. Nothing here is authored by the person building
the system, which is the point.

The six fields with no CUAD equivalent (incoterm, delivery_sla_hours, penalty_cap,
jurisdiction, payment_terms_days, force_majeure_events) are unlabelled and are reported as
unmeasured rather than being scored against a proxy.

    python -m eval.datasets.build_extraction_labels
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS = HERE / "corpus"
OUT = HERE / "extraction_labels.jsonl"

# CUAD clause category -> the schema field it grounds. One-to-one only: a category that
# would need interpretation to become a field is left out rather than stretched.
CATEGORY_TO_FIELD = {
    "Governing Law": "governing_law",
    "Cap On Liability": "liability_cap",
    "Insurance": "insurance_required",
    "Warranty Duration": "warranty_period_months",
    "Notice Period To Terminate Renewal": "termination_notice_days",
    "Renewal Term": "auto_renew",
    "Liquidated Damages": "penalty_per_day",
}

UNLABELLED_FIELDS = (
    "incoterm",
    "delivery_sla_hours",
    "penalty_cap",
    "jurisdiction",
    "payment_terms_days",
    "force_majeure_events",
)


def normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def locate(haystack: str, needle: str, hint: int) -> tuple[int, int] | None:
    needle = needle.strip()
    if not needle:
        return None
    window_start = max(0, hint - 200)
    local = haystack[window_start : hint + len(needle) + 200].find(needle)
    if local != -1:
        return window_start + local, window_start + local + len(needle)
    direct = haystack.find(needle)
    if direct != -1:
        return direct, direct + len(needle)
    pattern = re.compile(r"\s+".join(re.escape(part) for part in needle.split()))
    match = pattern.search(haystack)
    return (match.start(), match.end()) if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuad", type=Path, default=ROOT / "var" / "cuad" / "data" / "CUADv1.json")
    args = parser.parse_args()

    corpus = {path.stem for path in CORPUS.glob("*.txt")}
    payload = json.loads(args.cuad.read_text(encoding="utf-8"))

    records: list[dict[str, object]] = []
    discarded = 0
    for entry in payload["data"]:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", entry["title"]).strip("-")[:80]
        if slug not in corpus:
            continue
        context = normalise(entry["paragraphs"][0]["context"])
        for qa in entry["paragraphs"][0]["qas"]:
            category = qa["id"].split("__")[-1]
            field = CATEGORY_TO_FIELD.get(category)
            if field is None or qa.get("is_impossible") or not qa["answers"]:
                continue
            spans: list[tuple[int, int]] = []
            texts: list[str] = []
            for answer in qa["answers"]:
                located = locate(context, answer["text"], int(answer["answer_start"]))
                if located is None:
                    discarded += 1
                    continue
                spans.append(located)
                texts.append(context[located[0] : located[1]])
            if not spans:
                continue
            records.append(
                {
                    "document": slug,
                    "field": field,
                    "category": category,
                    "spans": spans,
                    "answers": texts,
                    "source": "cuad-v1-human-annotated",
                }
            )

    records.sort(key=lambda record: (record["document"], record["field"]))
    with OUT.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    print(
        json.dumps(
            {
                "labels": len(records),
                "documents": len({record["document"] for record in records}),
                "fields_labelled": sorted({str(record["field"]) for record in records}),
                "fields_unlabelled": list(UNLABELLED_FIELDS),
                "discarded_unlocatable": discarded,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
