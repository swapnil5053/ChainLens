"""Regenerate every results table in the documentation from eval/results/*.json.

No table in this repository is typed by hand. Running

    python -m eval.report

rewrites the marked regions in README.md and docs/RETRIEVAL.md, and refreshes
eval/baseline.json, which the CI regression gate compares against. A missing or blocked
cell renders as a dash and is explained in a footnote. It never renders as a number.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.bootstrap import ROOT

RESULTS_DIR = ROOT / "eval" / "results"
BASELINE_PATH = ROOT / "eval" / "baseline.json"
README = ROOT / "README.md"
RETRIEVAL_DOC = ROOT / "docs" / "RETRIEVAL.md"

START = "<!-- eval:{name}:start -->"
END = "<!-- eval:{name}:end -->"
BLOCKED_CELL = "--"

RETRIEVAL_LABELS = {
    "dense": "dense (pgvector cosine)",
    "mmr": "MMR (lambda 0.5)",
    "lexical": "lexical (Postgres FTS, ts_rank_cd)",
    "rrf": "RRF fusion (dense + lexical, k=60)",
    "rrf_expansion": "RRF fusion + glossary query expansion",
    "rrf_rerank": "RRF fusion + cross-encoder rerank",
}
ORDER = list(RETRIEVAL_LABELS)
CHUNKINGS = ["recursive-512", "recursive-1024", "clause-aware"]


def load_results() -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for path in sorted(RESULTS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        results[payload["run_id"]] = payload
    return results


def _cell(result: dict[str, Any] | None, key: str, digits: int = 3) -> str:
    if result is None or result.get("status") != "ok":
        return BLOCKED_CELL
    value = result["metrics"].get(key)
    return BLOCKED_CELL if value is None else f"{value:.{digits}f}"


def footnotes(results: dict[str, dict[str, Any]]) -> str:
    reasons: dict[str, list[str]] = {}
    for run_id, result in sorted(results.items()):
        if result.get("status") != "ok":
            reasons.setdefault(str(result.get("blocked_reason", "blocked")), []).append(run_id)
    if not reasons:
        return ""
    lines = ["", "Cells marked `--` were not measured:"]
    for reason, runs in reasons.items():
        lines.append(f"- {reason} ({len(runs)} configurations: `{'`, `'.join(runs)}`)")
    return "\n".join(lines)


def _row(label: str, result: dict[str, Any] | None, keys: list[tuple[str, int]]) -> str:
    return "| " + " | ".join([label, *[_cell(result, key, d) for key, d in keys]]) + " |"


def headline_table(results: dict[str, dict[str, Any]], chunking: str) -> str:
    keys = [
        ("recall@3", 3),
        ("recall@6", 3),
        ("recall@10", 3),
        ("mrr", 3),
        ("ndcg@10", 3),
        ("hit@6", 3),
        ("span_coverage@6", 3),
        ("latency_ms_p50", 1),
        ("latency_ms_p95", 1),
    ]
    lines = [
        f"Chunking fixed at `{chunking}`. Retrieval is scoped to the document the "
        "question is asked about.",
        "",
        "| retrieval | Recall@3 | Recall@6 | Recall@10 | MRR | nDCG@10 | hit@6 | "
        "answer chars shown @6 | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [_row(RETRIEVAL_LABELS[key], results.get(f"{chunking}__{key}"), keys) for key in ORDER]
    return "\n".join(lines) + footnotes(results)


def full_table(results: dict[str, dict[str, Any]]) -> str:
    keys = [
        ("recall@3", 3),
        ("recall@6", 3),
        ("recall@10", 3),
        ("mrr", 3),
        ("ndcg@10", 3),
        ("latency_ms_p50", 1),
        ("latency_ms_p95", 1),
    ]
    lines = [
        "| chunking | retrieval | Recall@3 | Recall@6 | Recall@10 | MRR | nDCG@10 | "
        "p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for chunking in CHUNKINGS:
        for key in ORDER:
            result = results.get(f"{chunking}__{key}")
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{chunking}`",
                        RETRIEVAL_LABELS[key],
                        *[_cell(result, name, digits) for name, digits in keys],
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + footnotes(results)


def latency_table(results: dict[str, dict[str, Any]], chunking: str) -> str:
    keys = [
        ("latency_ms_p50", 1),
        ("embed_ms_p50", 1),
        ("search_ms_p50", 1),
        ("latency_ms_p95", 1),
    ]
    lines = [
        "| retrieval | total p50 ms | query embedding p50 ms | Postgres search p50 ms | "
        "total p95 ms |",
        "|---|---|---|---|---|",
    ]
    lines += [_row(RETRIEVAL_LABELS[key], results.get(f"{chunking}__{key}"), keys) for key in ORDER]
    return "\n".join(lines) + footnotes(results)


def provenance(results: dict[str, dict[str, Any]]) -> str:
    ok = [result for result in results.values() if result.get("status") == "ok"]
    if not ok:
        return "No completed evaluation runs found in `eval/results/`."
    sample = ok[0]
    embedding = sample["environment"]["embedding"]
    dirty = " (working tree dirty at run time)" if sample.get("git_dirty") else ""
    return (
        f"Generated by `python -m eval.report` from {len(results)} files in "
        f"`eval/results/`. Runs produced at commit `{sample['git_sha'][:12]}`{dirty} on "
        f"{sample['created_at']}.\n\n"
        f"Dataset `{sample['dataset']['path']}`, sha256 "
        f"`{sample['dataset']['sha256'][:16]}`, {sample['dataset']['items']} questions "
        f"across {sample['dataset']['documents']} documents and "
        f"{sample['dataset']['categories']} clause categories. Embedding provider "
        f"`{embedding['provider']}` (dim {embedding['dim']}); Postgres "
        f"{sample['environment']['postgres']}.\n\n"
        "The embedding provider is not `bge-small-en-v1.5`: the model hub was unreachable "
        "in the environment these numbers were produced in, so a corpus-fitted LSA model "
        "was used instead. See ADR-0003. Absolute values are a floor for the architecture, "
        "not a claim about a modern encoder."
    )


def replace_region(path: Path, name: str, body: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    start, end = START.format(name=name), END.format(name=name)
    if start not in text or end not in text:
        return False
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    path.write_text(f"{head}{start}\n{body}\n{end}{tail}", encoding="utf-8")
    return True


def write_baseline(results: dict[str, dict[str, Any]], chunking: str) -> dict[str, Any]:
    best_id, best = None, -1.0
    for key in ORDER:
        result = results.get(f"{chunking}__{key}")
        if result and result.get("status") == "ok":
            value = float(result["metrics"].get("recall@6", 0.0))
            if value > best:
                best_id, best = f"{chunking}__{key}", value
    payload = {
        "note": "CI fails if recall@6 for this configuration drops more than 2 points.",
        "run_id": best_id,
        "recall@6": round(best, 4) if best_id else None,
        "tolerance": 0.02,
        "source": f"eval/results/{best_id}.json" if best_id else None,
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headline-chunking", default="clause-aware")
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()

    results = load_results()
    headline = headline_table(results, args.headline_chunking)
    updated = []
    for path, name, body in (
        (README, "headline", f"{headline}\n\n{provenance(results)}"),
        (RETRIEVAL_DOC, "headline", headline),
        (RETRIEVAL_DOC, "full", full_table(results)),
        (RETRIEVAL_DOC, "latency", latency_table(results, args.headline_chunking)),
        (RETRIEVAL_DOC, "provenance", provenance(results)),
    ):
        if replace_region(path, name, body):
            updated.append(f"{path.name}:{name}")

    baseline = write_baseline(results, args.headline_chunking)
    print(json.dumps({"updated": updated, "baseline": baseline}, indent=2))
    if args.print:
        print(headline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
