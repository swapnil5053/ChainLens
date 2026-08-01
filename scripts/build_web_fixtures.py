"""Generate the web application's fixtures from the real evaluation corpus.

The mock adapter is not allowed to invent contract text. Everything it serves comes from
`eval/datasets/corpus/`, chunked by the same splitters the API uses, so the spans the
interface highlights are the spans the backend would return.

Only offsets are stored, never chunk text: the browser slices `fullText` to reconstruct a
chunk, which is the same invariant `test_offsets.py` asserts server-side. It keeps the
fixtures small and it means a wrong offset shows up on screen rather than hiding.

    python scripts/build_web_fixtures.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from chainlens.ingest.chunk import chunk_document  # noqa: E402
from chainlens.ingest.parse import parse_text  # noqa: E402

CORPUS = ROOT / "eval" / "datasets" / "corpus"
OUT = ROOT / "apps" / "web" / "public" / "fixtures"
STRATEGIES = ("clause-aware", "recursive-512")

# Both arms are measured at clause-aware chunking, so the comparison isolates the
# retrieval strategy rather than confounding it with a chunking change. The v1 default
# combined MMR with recursive chunking and scored worse still; that run is carried as a
# reference so the view can say so without a second grid lookup.
ARM_RUNS = {"mmr": "clause-aware__mmr", "clause-rrf-expansion": "clause-aware__rrf_expansion"}
REFERENCE_RUNS = {"v1-equivalent": "recursive-512__mmr"}


def title_from_slug(slug: str) -> str:
    return re.sub(r"\s+", " ", slug.replace("-", " ")).strip()


def party_from_slug(slug: str) -> str:
    head = slug.split("-")[0]
    return head.title() if head else "Unknown"


def kind_from_slug(slug: str) -> str:
    upper = slug.upper()
    for needle, label in (
        ("DISTRIBUTOR", "Distribution"),
        ("DISTRIBUTION", "Distribution"),
        ("SUPPLY", "Supply"),
        ("MANUFACTUR", "Manufacturing"),
        ("TRANSPORTATION", "Transportation"),
        ("LOGISTICS", "Logistics"),
        ("RESELLER", "Reseller"),
        ("OUTSOURCING", "Outsourcing"),
        ("STRATEGIC", "Strategic alliance"),
        ("SERVICE", "Services"),
    ):
        if needle in upper:
            return label
    return "Agreement"


def _evidence(run_id: str) -> dict[str, object]:
    payload = json.loads(
        (ROOT / "eval" / "results" / f"{run_id}.json").read_text(encoding="utf-8")
    )
    metrics = payload["metrics"]
    return {
        "runId": run_id,
        "recallAt6": metrics["recall@6"],
        "mrr": metrics["mrr"],
        "ndcgAt10": metrics["ndcg@10"],
        "latencyMsP50": metrics["latency_ms_p50"],
        "embedMsP50": metrics["embed_ms_p50"],
        "searchMsP50": metrics["search_ms_p50"],
        "questions": metrics["n_evaluated"],
        "datasetSha256": payload["dataset"]["sha256"][:16],
        "embeddingProvider": payload["environment"]["embedding"]["provider"],
    }


def main() -> int:
    (OUT / "contracts").mkdir(parents=True, exist_ok=True)

    index: list[dict[str, object]] = []
    for path in sorted(CORPUS.glob("*.txt")):
        slug = path.stem
        parsed = parse_text(path.read_text(encoding="utf-8"), f"{slug}.txt")

        chunk_sets: dict[str, list[dict[str, object]]] = {}
        for strategy in STRATEGIES:
            chunk_sets[strategy] = [
                {
                    "id": f"{slug}:{strategy}:{chunk.ordinal}",
                    "ordinal": chunk.ordinal,
                    "page": chunk.page,
                    "start": chunk.char_start,
                    "end": chunk.char_end,
                    "clauseId": chunk.clause_id,
                    "clauseTitle": chunk.clause_title,
                }
                for chunk in chunk_document(parsed, strategy)
            ]

        clause_chunks = chunk_sets["clause-aware"]
        (OUT / "contracts" / f"{slug}.json").write_text(
            json.dumps(
                {
                    "id": slug,
                    "title": title_from_slug(slug),
                    "pageCount": parsed.page_count,
                    "charCount": len(parsed.full_text),
                    "fullText": parsed.full_text,
                    "chunks": chunk_sets,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        index.append(
            {
                "id": slug,
                "title": title_from_slug(slug),
                "party": party_from_slug(slug),
                "kind": kind_from_slug(slug),
                "pageCount": parsed.page_count,
                "charCount": len(parsed.full_text),
                "clauseCount": sum(1 for c in clause_chunks if c["clauseId"]),
                "chunkCount": len(clause_chunks),
            }
        )

    (OUT / "index.json").write_text(
        json.dumps({"contracts": index}, separators=(",", ":")), encoding="utf-8"
    )
    evidence = {arm: _evidence(run) for arm, run in ARM_RUNS.items()}
    evidence.update({label: _evidence(run) for label, run in REFERENCE_RUNS.items()})
    (OUT / "arms.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    sizes = [f.stat().st_size for f in (OUT / "contracts").glob("*.json")]
    print(
        json.dumps(
            {"contracts": len(index), "bytes_total": sum(sizes), "bytes_largest": max(sizes)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
