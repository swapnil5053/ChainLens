"""Run the extraction evaluation.

    python -m eval.run_extraction

Needs no database and no network: it parses the committed corpus, runs the deterministic
extractors, and scores them against the committed CUAD-derived labels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.bootstrap import ROOT
from eval.runners.extraction import run_extraction_eval


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "eval" / "datasets" / "corpus")
    parser.add_argument(
        "--labels", type=Path, default=ROOT / "eval" / "datasets" / "extraction_labels.jsonl"
    )
    parser.add_argument("--results", type=Path, default=ROOT / "eval" / "results")
    args = parser.parse_args()

    result = run_extraction_eval(
        corpus_dir=args.corpus, labels_path=args.labels, results_dir=args.results
    )
    metrics = result["metrics"]
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "documents": result["dataset"]["documents"],
                "labels": result["dataset"]["labels"],
                "micro": metrics["micro"],
                "macro_precision": metrics["macro_precision"],
                "macro_recall": metrics["macro_recall"],
            },
            indent=2,
        )
    )
    for field, scores in metrics["per_field"].items():
        print(
            f"  {field:26} P={scores['precision']:.3f} R={scores['recall']:.3f} "
            f"F1={scores['f1']:.3f}  tp={scores['tp']} fp={scores['fp']} fn={scores['fn']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
