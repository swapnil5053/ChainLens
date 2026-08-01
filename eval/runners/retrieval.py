"""The retrieval evaluation runner."""

from __future__ import annotations

import json
import platform
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from chainlens.embeddings.base import EmbeddingProvider
from chainlens.ingest.hashing import sha256_text
from chainlens.retrieval.rerank import Reranker
from chainlens.retrieval.service import RetrievalConfig, RetrievalService

from .metrics import (
    hit_at_k,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
    relevance_flags,
    span_coverage,
)


@dataclass(slots=True)
class GoldenRecord:
    qa_id: str
    document: str
    category: str
    question: str
    spans: list[tuple[int, int]]


def load_golden(path: Path) -> list[GoldenRecord]:
    records: list[GoldenRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        records.append(
            GoldenRecord(
                qa_id=payload["qa_id"],
                document=payload["document"],
                category=payload["category"],
                question=payload["question"],
                spans=[(int(start), int(end)) for start, end in payload["spans"]],
            )
        )
    return records


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


def document_ids(session: Session) -> dict[str, uuid.UUID]:
    rows = session.execute(text("SELECT id, filename FROM documents")).all()
    return {row.filename.removesuffix(".txt"): row.id for row in rows}


def count_relevant(
    session: Session, document_id: uuid.UUID, index_name: str, spans: list[tuple[int, int]]
) -> int:
    clauses = " OR ".join(
        f"(c.char_start < :end{i} AND :start{i} < c.char_end)" for i in range(len(spans))
    )
    params: dict[str, Any] = {"document_id": str(document_id), "index_name": index_name}
    for index, (start, end) in enumerate(spans):
        params[f"start{index}"] = start
        params[f"end{index}"] = end
    sql = text(
        f"""
        SELECT count(*) FROM chunks c
        WHERE c.document_id = CAST(:document_id AS uuid)
          AND c.index_name = :index_name
          AND ({clauses})
        """
    )
    return int(session.execute(sql, params).scalar_one())


def run_retrieval_eval(
    session: Session,
    *,
    golden: list[GoldenRecord],
    golden_path: Path,
    embedder: EmbeddingProvider,
    config: RetrievalConfig,
    k_values: tuple[int, ...],
    run_id: str,
    reranker: Reranker | None = None,
    blocked_reason: str | None = None,
) -> dict[str, Any]:
    sha, dirty = git_sha()
    envelope: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha,
        "git_dirty": dirty,
        "dataset": {
            "path": "eval/datasets/" + golden_path.name,
            "sha256": sha256_text(golden_path.read_text(encoding="utf-8")),
            "items": len(golden),
            "documents": len({record.document for record in golden}),
            "categories": len({record.category for record in golden}),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "postgres": str(session.execute(text("SHOW server_version")).scalar_one()),
            "embedding": embedder.describe(),
        },
        "config": config.to_dict() | {"config_hash": config.hash},
        "scope": "document",
    }

    if blocked_reason is not None:
        return envelope | {
            "status": "blocked",
            "blocked_reason": blocked_reason,
            "metrics": {},
            "per_query": [],
        }

    if getattr(embedder, "is_fake", False):
        return envelope | {
            "status": "blocked",
            "blocked_reason": (
                "refusing to record metrics produced with the stub embedding provider"
            ),
            "metrics": {},
            "per_query": [],
        }

    service = RetrievalService(embedder, reranker)
    ids = document_ids(session)
    per_query: list[dict[str, Any]] = []
    latencies: list[float] = []
    embed_latencies: list[float] = []
    search_latencies: list[float] = []
    context_tokens: list[float] = []
    skipped: list[str] = []
    max_k = max(k_values)

    for record in golden:
        document_id = ids.get(record.document)
        if document_id is None:
            skipped.append(record.qa_id)
            continue
        relevant_total = count_relevant(session, document_id, config.index_name, record.spans)
        if relevant_total == 0:
            skipped.append(record.qa_id)
            continue
        search_config = RetrievalConfig(**(config.to_dict() | {"k": max_k}))
        started = time.perf_counter()
        hits, trace = service.search(
            session, record.question, config=search_config, document_id=document_id
        )
        elapsed = (time.perf_counter() - started) * 1000
        spans = [(hit.char_start, hit.char_end) for hit in hits]
        flags = relevance_flags(spans, record.spans)
        latencies.append(elapsed)
        embed_latencies.append(trace.embed_ms)
        search_latencies.append(trace.dense_ms + trace.lexical_ms)
        context_tokens.append(float(sum(hit.token_estimate for hit in hits[: config.k])))
        per_query.append(
            {
                "qa_id": record.qa_id,
                "category": record.category,
                "relevant_total": relevant_total,
                "ranks_hit": [index + 1 for index, flag in enumerate(flags) if flag],
                "reciprocal_rank": round(reciprocal_rank(flags), 4),
                "recall": {
                    str(k): round(recall_at_k(flags, relevant_total, k), 4) for k in k_values
                },
                "hit": {str(k): hit_at_k(flags, k) for k in k_values},
                "ndcg_10": round(ndcg_at_k(flags, relevant_total, 10), 4),
                "span_coverage": {
                    str(k): round(span_coverage(spans, record.spans, k), 4) for k in k_values
                },
                "latency_ms": round(elapsed, 2),
                "trace": trace.to_dict(),
            }
        )

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    return envelope | {
        "status": "ok",
        "blocked_reason": None,
        "skipped_qa_ids": skipped,
        "metrics": {
            "n_evaluated": len(per_query),
            "n_skipped": len(skipped),
            **{f"recall@{k}": mean([row["recall"][str(k)] for row in per_query]) for k in k_values},
            **{f"hit@{k}": mean([row["hit"][str(k)] for row in per_query]) for k in k_values},
            "mrr": mean([row["reciprocal_rank"] for row in per_query]),
            "ndcg@10": mean([row["ndcg_10"] for row in per_query]),
            **{
                f"span_coverage@{k}": mean([row["span_coverage"][str(k)] for row in per_query])
                for k in k_values
            },
            "latency_ms_p50": round(percentile(latencies, 0.5), 2),
            "latency_ms_p95": round(percentile(latencies, 0.95), 2),
            "embed_ms_p50": round(percentile(embed_latencies, 0.5), 2),
            "search_ms_p50": round(percentile(search_latencies, 0.5), 2),
            "context_tokens_p50": round(percentile(context_tokens, 0.5), 1),
            "generation_cost_usd": None,
        },
        "per_query": per_query,
    }


def write_result(result: dict[str, Any], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result['run_id']}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path
