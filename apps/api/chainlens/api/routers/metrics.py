from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from ...db.models import Query
from ...db.session import session_scope
from ...paths import EVAL_RESULTS_DIR
from ..schemas import MetricsSummary

router = APIRouter(tags=["metrics"])


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return round(ordered[index], 2)


@router.get("/metrics/summary", response_model=MetricsSummary)
def metrics_summary(window: int = 200) -> MetricsSummary:
    with session_scope() as session:
        rows = list(
            session.execute(select(Query).order_by(Query.created_at.desc()).limit(window)).scalars()
        )
    retrieval = [row.retrieval_ms for row in rows]
    generation = [row.generation_ms for row in rows]
    return MetricsSummary(
        window=window,
        queries=len(rows),
        retrieval_ms_p50=_percentile(retrieval, 0.5),
        retrieval_ms_p95=_percentile(retrieval, 0.95),
        generation_ms_p50=_percentile(generation, 0.5),
        generation_ms_p95=_percentile(generation, 0.95),
        cost_usd_total=round(sum(row.cost_usd for row in rows), 6),
        note=(
            "Cost is estimated from measured token counts at published Gemini 2.5 Flash "
            "rates. It is zero when no generation provider is configured."
        ),
    )


@router.get("/eval/results")
def eval_results(directory: Path = EVAL_RESULTS_DIR) -> list[dict[str, Any]]:
    """Serve the committed evaluation artifacts.

    The Evaluation screen reads this. It deliberately reads the same files that are
    committed to the repository, so what the screen shows and what the README claims
    cannot drift apart.
    """
    payloads: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.pop("per_query", None)
        payloads.append(payload)
    return payloads


@router.get("/eval/results/{run_id}")
def eval_result(run_id: str, directory: Path = EVAL_RESULTS_DIR) -> dict[str, Any]:
    path = directory / f"{run_id}.json"
    if not path.is_file() or path.parent != directory:
        return {"error": "unknown run id", "run_id": run_id}
    return dict(json.loads(path.read_text(encoding="utf-8")))
