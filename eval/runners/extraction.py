"""Field-level precision and recall for the extraction schema.

Scoring, stated precisely because the definition is where this kind of measurement usually
gets flattered:

  true positive   the extractor emitted the field and its span overlaps a human-annotated
                  span for that field in that document
  false positive  the extractor emitted the field and the span does not overlap, or the
                  extractor emitted the field for a document where the annotators recorded
                  no such clause
  false negative  a human annotation exists and the extractor emitted nothing

Span overlap rather than string equality is deliberate. The extractor reads "thirty (30)
days prior written notice" and returns 30; the annotator highlighted the sentence. Asking
those to be string-equal would measure formatting, not extraction. What overlap does test
is the thing that matters for the product: does the value point at the right sentence.

The six fields with no CUAD equivalent are reported with status "unlabelled" and no
numbers, rather than being scored against a proxy.
"""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chainlens.extraction.extractors import extract_document
from chainlens.extraction.risk import assess
from chainlens.extraction.schema import FIELD_NAMES, ContractExtraction
from chainlens.ingest.hashing import sha256_text
from chainlens.ingest.parse import parse_text

# Where the CUAD category is broader than the schema field it was mapped to, the score is
# still reported, because deleting a zero looks like hiding one. The reason it is a floor
# rather than a fair measurement is recorded alongside it.
KNOWN_MISMATCHES = {
    "penalty_per_day": (
        "The CUAD category 'Liquidated Damages' annotates termination fees and cancellation "
        "charges generally, while this field is specifically a per-day rate. Most annotated "
        "clauses in this corpus contain no per-day figure at all, so a recall of zero here "
        "is mostly a mapping mismatch rather than an extraction failure."
    ),
    "liability_cap": (
        "Eight of the 29 corpus documents redact commercial figures as [***], so a numeric "
        "cap is unavailable in the source for those. The extractor emits the qualitative "
        "limitation instead, which the risk rule liability-cap-language-only then flags."
    ),
    "warranty_period_months": (
        "'Warranty Duration' annotations frequently mark a warranty clause that states no "
        "duration, for example one that incorporates a standard warranty by reference. "
        "Those are unrecoverable as a number by any extractor."
    ),
}

UNLABELLED = (
    "incoterm",
    "delivery_sla_hours",
    "penalty_cap",
    "jurisdiction",
    "payment_terms_days",
    "force_majeure_events",
)


def git_sha() -> tuple[str, bool]:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        )
        return sha, dirty
    except Exception:  # pragma: no cover
        return "unknown", False


def load_labels(path: Path) -> dict[tuple[str, str], list[tuple[int, int]]]:
    labels: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        key = (record["document"], record["field"])
        labels[key] = [(int(start), int(end)) for start, end in record["spans"]]
    return labels


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def run_extraction_eval(
    *,
    corpus_dir: Path,
    labels_path: Path,
    results_dir: Path,
    run_id: str = "extraction__cuad",
) -> dict[str, Any]:
    labels = load_labels(labels_path)
    documents = sorted(corpus_dir.glob("*.txt"))
    labelled_fields = sorted({field for _, field in labels})

    counts: dict[str, dict[str, int]] = {
        field: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for field in labelled_fields
    }
    emitted: dict[str, int] = dict.fromkeys(FIELD_NAMES, 0)
    per_document: list[dict[str, Any]] = []
    extractions: list[ContractExtraction] = []
    flag_counts: dict[str, int] = {}
    total_ms = 0.0

    for path in documents:
        slug = path.stem
        parsed = parse_text(path.read_text(encoding="utf-8"), f"{slug}.txt")
        extraction = extract_document(parsed, document_id=slug)
        extractions.append(extraction)
        total_ms += extraction.elapsed_ms

        for name, entry in extraction.fields.items():
            emitted[name] += 1
            # The span must resolve against the document, every time, for every field.
            assert parsed.full_text[entry.char_start : entry.char_end], "unverified span emitted"

        document_rows: dict[str, str] = {}
        for field in labelled_fields:
            gold = labels.get((slug, field))
            got = extraction.fields.get(field)
            if gold and got:
                span = (got.char_start, got.char_end)
                if any(overlaps(span, gold_span) for gold_span in gold):
                    counts[field]["tp"] += 1
                    document_rows[field] = "tp"
                else:
                    counts[field]["fp"] += 1
                    document_rows[field] = "fp-wrong-span"
            elif gold and not got:
                counts[field]["fn"] += 1
                document_rows[field] = "fn"
            elif got and not gold:
                counts[field]["fp"] += 1
                document_rows[field] = "fp-no-annotation"
            else:
                counts[field]["tn"] += 1
                document_rows[field] = "tn"

        report = assess(extraction)
        for flag in report.flags:
            flag_counts[flag.rule_id] = flag_counts.get(flag.rule_id, 0) + 1

        per_document.append(
            {
                "document": slug,
                "fields_extracted": sorted(extraction.fields),
                "outcomes": document_rows,
                "risk_flags": [flag.rule_id for flag in report.flags],
                "elapsed_ms": extraction.elapsed_ms,
            }
        )

    def score(tp: int, fp: int, fn: int) -> dict[str, float | int]:
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    per_field = {
        field: score(counts[field]["tp"], counts[field]["fp"], counts[field]["fn"])
        for field in labelled_fields
    }
    micro = score(
        sum(counts[f]["tp"] for f in labelled_fields),
        sum(counts[f]["fp"] for f in labelled_fields),
        sum(counts[f]["fn"] for f in labelled_fields),
    )
    macro_precision = sum(float(per_field[f]["precision"]) for f in labelled_fields) / len(
        labelled_fields
    )
    macro_recall = sum(float(per_field[f]["recall"]) for f in labelled_fields) / len(labelled_fields)

    sha, dirty = git_sha()
    result: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha,
        "git_dirty": dirty,
        "extractor": "deterministic-v1",
        "dataset": {
            "labels_path": "eval/datasets/extraction_labels.jsonl",
            "sha256": sha256_text(labels_path.read_text(encoding="utf-8")),
            "labels": len(labels),
            "documents": len(documents),
            "source": "cuad-v1-human-annotated",
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "scoring": {
            "match": "span overlap between the emitted field span and a human-annotated span",
            "false_positive": "wrong span, or a field emitted where annotators recorded no clause",
        },
        "status": "ok",
        "metrics": {
            "micro": micro,
            "macro_precision": round(macro_precision, 4),
            "macro_recall": round(macro_recall, 4),
            "per_field": per_field,
            "fields_labelled": labelled_fields,
            "fields_unlabelled": list(UNLABELLED),
            "known_mismatches": KNOWN_MISMATCHES,
            "emitted_per_field": emitted,
            "mean_elapsed_ms": round(total_ms / max(1, len(documents)), 2),
        },
        "risk": {
            "rules_evaluated": assess(extractions[0]).rules_evaluated if extractions else 0,
            "flags_by_rule": dict(sorted(flag_counts.items(), key=lambda item: -item[1])),
        },
        "per_document": per_document,
    }

    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{run_id}.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
