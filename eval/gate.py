"""The CI regression gate.

Fails the build when Recall@6 for the baseline configuration drops more than the
committed tolerance below `eval/baseline.json`. Blocked runs never satisfy the gate:
a configuration that could not be measured is a failure to measure, not a pass.

    python -m eval.gate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.bootstrap import ROOT

RESULTS_DIR = ROOT / "eval" / "results"
BASELINE_PATH = ROOT / "eval" / "baseline.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    if not args.baseline.exists():
        print(f"no baseline at {args.baseline}; run 'python -m eval.report' first")
        return 1
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    run_id, expected, tolerance = (
        baseline["run_id"],
        baseline["recall@6"],
        float(baseline["tolerance"]),
    )

    current_path = args.results / f"{run_id}.json"
    if not current_path.exists():
        print(f"baseline configuration {run_id} produced no result file")
        return 1
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if current.get("status") != "ok":
        print(f"{run_id} is {current.get('status')}: {current.get('blocked_reason')}")
        return 1

    measured = float(current["metrics"]["recall@6"])
    delta = measured - float(expected)
    verdict = "pass" if delta >= -tolerance else "fail"
    print(
        json.dumps(
            {
                "run_id": run_id,
                "baseline_recall@6": expected,
                "measured_recall@6": round(measured, 4),
                "delta": round(delta, 4),
                "tolerance": tolerance,
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
