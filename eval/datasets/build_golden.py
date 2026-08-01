"""Build the golden retrieval set from CUAD.

Provenance and method are documented in ``eval/datasets/README.md``. In short: the
contracts and the answer spans are CUAD v1, human-annotated by lawyers, CC BY 4.0; the
question phrasing is generated from a committed template per clause category; and every
pair is verified by locating the annotated answer inside the parsed document. Any pair
whose span cannot be located is discarded rather than approximated.

    python -m eval.datasets.build_golden --cuad var/cuad/data/CUADv1.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS_DIR = HERE / "corpus"
GOLDEN_PATH = HERE / "golden.jsonl"
TEMPLATES_PATH = HERE / "questions.yaml"

SUPPLY_CHAIN_TITLE_HINTS = (
    "DISTRIBUTOR",
    "DISTRIBUTION",
    "SUPPLY",
    "MANUFACTURING",
    "MANUFACTURE",
    "TRANSPORTATION",
    "LOGISTICS",
    "RESELLER",
    "OUTSOURCING",
    "STRATEGIC ALLIANCE",
    "SERVICE",
)


@dataclass(frozen=True, slots=True)
class GoldenItem:
    qa_id: str
    document: str
    category: str
    question: str
    cuad_question: str
    answers: tuple[str, ...]
    spans: tuple[tuple[int, int], ...]
    question_source: str
    answer_source: str


def load_templates() -> dict[str, str]:
    payload: dict[str, Any] = yaml.safe_load(TEMPLATES_PATH.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in payload["categories"].items()}


def normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def locate(haystack: str, needle: str, hint: int) -> tuple[int, int] | None:
    """Find the annotated answer inside the normalised text.

    Tries the annotated offset first, then an exact search, then a whitespace-tolerant
    search. Returns None when the span genuinely is not present, in which case the pair
    is discarded.
    """
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


def build(
    cuad_path: Path,
    *,
    max_documents: int,
    target_pairs: int,
    min_chars: int,
    max_chars: int,
    seed: int,
) -> tuple[list[GoldenItem], dict[str, str], dict[str, Any]]:
    templates = load_templates()
    payload = json.loads(cuad_path.read_text(encoding="utf-8"))
    rng = random.Random(seed)

    candidates: list[tuple[dict[str, Any], str, int]] = []
    for entry in payload["data"]:
        if not any(hint in entry["title"].upper() for hint in SUPPLY_CHAIN_TITLE_HINTS):
            continue
        context = normalise(entry["paragraphs"][0]["context"])
        if not min_chars <= len(context) <= max_chars:
            continue
        answered = sum(
            1
            for qa in entry["paragraphs"][0]["qas"]
            if not qa.get("is_impossible")
            and qa["answers"]
            and qa["id"].split("__")[-1] in templates
        )
        if answered >= 4:
            candidates.append((entry, context, answered))

    candidates.sort(key=lambda item: (-item[2], item[0]["title"]))
    selected = candidates[: max_documents * 2]
    rng.shuffle(selected)
    selected = sorted(selected[:max_documents], key=lambda item: item[0]["title"])

    corpus: dict[str, str] = {}
    per_category: dict[str, list[GoldenItem]] = defaultdict(list)
    stats: dict[str, Any] = {"discarded_unlocatable": 0, "considered": 0}

    for entry, context, _ in selected:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", entry["title"]).strip("-")[:80]
        corpus[slug] = context
        for qa in entry["paragraphs"][0]["qas"]:
            category = qa["id"].split("__")[-1]
            if category not in templates or qa.get("is_impossible") or not qa["answers"]:
                continue
            stats["considered"] += 1
            spans: list[tuple[int, int]] = []
            texts: list[str] = []
            for answer in qa["answers"]:
                found = locate(context, answer["text"], int(answer["answer_start"]))
                if found is None:
                    continue
                spans.append(found)
                texts.append(context[found[0] : found[1]])
            if not spans:
                stats["discarded_unlocatable"] += 1
                continue
            per_category[category].append(
                GoldenItem(
                    qa_id=f"{slug}__{category}",
                    document=slug,
                    category=category,
                    question=templates[category],
                    cuad_question=qa["question"],
                    answers=tuple(texts),
                    spans=tuple(spans),
                    question_source="generated-from-committed-template",
                    answer_source="cuad-v1-human-annotated",
                )
            )

    # Balance across categories so no single clause type dominates the metric.
    ordered = sorted(per_category.items(), key=lambda pair: pair[0])
    for _, bucket in ordered:
        rng.shuffle(bucket)
    items: list[GoldenItem] = []
    index = 0
    while len(items) < target_pairs:
        added = False
        for _, bucket in ordered:
            if index < len(bucket):
                items.append(bucket[index])
                added = True
                if len(items) >= target_pairs:
                    break
        if not added:
            break
        index += 1

    items.sort(key=lambda item: item.qa_id)
    used = {item.document for item in items}
    corpus = {slug: text for slug, text in corpus.items() if slug in used}
    stats["kept_pairs"] = len(items)
    stats["documents"] = len(corpus)
    stats["categories"] = len({item.category for item in items})
    return items, corpus, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuad", type=Path, default=ROOT / "var" / "cuad" / "data" / "CUADv1.json")
    parser.add_argument("--max-documents", type=int, default=30)
    parser.add_argument("--target-pairs", type=int, default=110)
    parser.add_argument("--min-chars", type=int, default=20_000)
    parser.add_argument("--max-chars", type=int, default=90_000)
    parser.add_argument("--seed", type=int, default=20240101)
    args = parser.parse_args()

    items, corpus, stats = build(
        args.cuad,
        max_documents=args.max_documents,
        target_pairs=args.target_pairs,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        seed=args.seed,
    )

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for slug, text in corpus.items():
        (CORPUS_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")
    with GOLDEN_PATH.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(asdict(item), sort_keys=True) + "\n")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
