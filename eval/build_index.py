"""Build the evaluation indexes.

Parses the committed corpus once, then writes one index per chunking strategy so the
ablation can compare them without re-parsing. The embedding model is fitted once, at a
fixed granularity (``recursive-512``), and reused for every strategy: refitting per
strategy would confound the chunking comparison with a different embedding space each
time.

    CHAINLENS_LOCAL_PG=1 python -m eval.build_index --strategy clause-aware
"""

from __future__ import annotations

import argparse
import json
import time

from eval.bootstrap import ROOT, ensure_database

ensure_database()

from chainlens.db.session import session_scope
from chainlens.embeddings.lsa import LsaEmbeddings
from chainlens.embeddings.registry import DEFAULT_LSA_ARTIFACT
from chainlens.ingest.chunk import chunk_document
from chainlens.ingest.parse import parse_text
from chainlens.ingest.pipeline import index_parsed_document

CORPUS_DIR = ROOT / "eval" / "datasets" / "corpus"
STRATEGIES = ("recursive-512", "recursive-1024", "clause-aware")
FIT_STRATEGY = "recursive-512"


def load_corpus() -> list[tuple[str, str]]:
    return sorted(
        (path.stem, path.read_text(encoding="utf-8")) for path in CORPUS_DIR.glob("*.txt")
    )


def fit_embedder(force: bool = False) -> LsaEmbeddings:
    if DEFAULT_LSA_ARTIFACT.exists() and not force:
        return LsaEmbeddings.load(DEFAULT_LSA_ARTIFACT)
    texts: list[str] = []
    for name, raw in load_corpus():
        parsed = parse_text(raw, f"{name}.txt")
        texts.extend(chunk.text for chunk in chunk_document(parsed, FIT_STRATEGY))
    start = time.perf_counter()
    model = LsaEmbeddings().fit(texts)
    model.save(DEFAULT_LSA_ARTIFACT)
    print(
        json.dumps(
            {"fit_texts": len(texts), "fit_ms": round((time.perf_counter() - start) * 1000, 1)}
        )
    )
    return model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", action="append", choices=list(STRATEGIES))
    parser.add_argument("--refit", action="store_true")
    args = parser.parse_args()

    embedder = fit_embedder(force=args.refit)
    corpus = load_corpus()
    for strategy in args.strategy or list(STRATEGIES):
        started = time.perf_counter()
        chunk_total = clause_total = 0
        with session_scope() as session:
            for name, raw in corpus:
                result = index_parsed_document(
                    session,
                    parse_text(raw, f"{name}.txt"),
                    embedder=embedder,
                    chunk_strategy=strategy,
                    index_name=strategy,
                    meta={"corpus": "cuad-supply-chain-subset"},
                )
                chunk_total += result.chunk_count
                clause_total += result.clause_count
        print(
            json.dumps(
                {
                    strategy: {
                        "documents": len(corpus),
                        "chunks": chunk_total,
                        "chunks_with_clause_id": clause_total,
                        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                }
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
