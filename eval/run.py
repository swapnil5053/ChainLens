"""Evaluation entry point.

    CHAINLENS_LOCAL_PG=1 python -m eval.run --sweep eval/configs/ablation.yaml

Each grid cell writes exactly one JSON file into ``eval/results/``. Cells already
written are skipped unless ``--force`` is passed, so a sweep can be resumed after an
interruption without losing or silently reusing anything.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from eval.bootstrap import ROOT, ensure_database

ensure_database()

from chainlens.db.session import session_scope
from chainlens.embeddings.lsa import LsaEmbeddings
from chainlens.embeddings.registry import DEFAULT_LSA_ARTIFACT
from chainlens.retrieval.rerank import CrossEncoderReranker
from chainlens.retrieval.service import RetrievalConfig
from eval.runners.retrieval import load_golden, run_retrieval_eval, write_result

RESULTS_DIR = ROOT / "eval" / "results"
DATASET_DIR = ROOT / "eval" / "datasets"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep", type=Path, default=ROOT / "eval" / "configs" / "ablation.yaml")
    parser.add_argument("--only", action="append", help="run only these retrieval ids")
    parser.add_argument("--chunking", action="append", help="run only these chunkings")
    parser.add_argument("--k", action="append", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    spec: dict[str, Any] = yaml.safe_load(args.sweep.read_text(encoding="utf-8"))
    golden_path = DATASET_DIR / spec["dataset"]
    golden = load_golden(golden_path)
    k_values = tuple(args.k or spec["k_values"])

    embedder = LsaEmbeddings.load(DEFAULT_LSA_ARTIFACT)
    reranker = CrossEncoderReranker()
    rerank_error = reranker.error

    for chunking in args.chunking or spec["chunking"]:
        for retrieval in spec["retrieval"]:
            if args.only and retrieval["id"] not in args.only:
                continue
            # k is a reporting depth, not a retrieval setting: one run retrieves to
            # max(k) and every k in the grid is scored from the same ranking. Three
            # near-identical files per cell would only invite the reader to assume
            # three separate measurements happened.
            run_id = f"{chunking}__{retrieval['id']}"
            target = RESULTS_DIR / f"{run_id}.json"
            if target.exists() and not args.force:
                continue
            config = RetrievalConfig(
                strategy=retrieval["strategy"],
                k=max(k_values),
                fetch_k=spec["fetch_k"],
                rrf_k=spec["rrf_k"],
                mmr_lambda=spec["mmr_lambda"],
                expansion=bool(retrieval.get("expansion", False)),
                index_name=chunking,
                chunk_strategy=chunking,
            )
            blocked = None
            if retrieval.get("requires") == "cross-encoder-weights" and not reranker.available:
                blocked = (
                    f"cross-encoder weights could not be loaded: {rerank_error or 'unknown error'}"
                )
            with session_scope() as session:
                result = run_retrieval_eval(
                    session,
                    golden=golden,
                    golden_path=golden_path,
                    embedder=embedder,
                    config=config,
                    k_values=k_values,
                    run_id=run_id,
                    reranker=reranker,
                    blocked_reason=blocked,
                )
            path = write_result(result, RESULTS_DIR)
            print(
                json.dumps(
                    {
                        "wrote": path.name,
                        "status": result["status"],
                        "recall@6": result["metrics"].get("recall@6"),
                        "mrr": result["metrics"].get("mrr"),
                    }
                ),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
