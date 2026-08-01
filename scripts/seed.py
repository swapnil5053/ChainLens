"""Seed the database so the application is not empty on first run.

The three seed contracts are real supply-chain agreements from the committed CUAD corpus,
not invented ones. Fake demo data makes a real interface look fake, and a reviewer opening
this for the first time should see the kind of document the system is actually for.

    CHAINLENS_LOCAL_PG=1 python scripts/seed.py
    python scripts/seed.py --count 5          # against a configured DATABASE_URL

Idempotent: content hashing means running it twice indexes nothing the second time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.bootstrap import ensure_database

ensure_database()

from chainlens.config import get_settings
from chainlens.db.session import session_scope
from chainlens.embeddings.lsa import LsaEmbeddings
from chainlens.embeddings.registry import DEFAULT_LSA_ARTIFACT
from chainlens.ingest.chunk import chunk_document
from chainlens.ingest.parse import parse_text
from chainlens.ingest.pipeline import index_parsed_document

CORPUS = ROOT / "eval" / "datasets" / "corpus"

# Chosen for variety rather than convenience: a manufacturing and supply agreement, a
# distribution agreement and an outsourcing agreement exercise different clause vocabulary.
PREFERRED = (
    "Apollo-Endosurgery-Manufacturing-and-Supply-Agreement",
    "BELLRINGBRANDS-INC-02-07-2020-EX-10-18-MASTER-SUPPLY-AGREEMENT",
    "BNLFINANCIALCORP-03-30-2007-EX-10-8-OUTSOURCING-AGREEMENT",
)


def pick(count: int) -> list[Path]:
    available = {path.stem: path for path in CORPUS.glob("*.txt")}
    chosen = [available[name] for name in PREFERRED if name in available]
    for name in sorted(available):
        if len(chosen) >= count:
            break
        if available[name] not in chosen:
            chosen.append(available[name])
    return chosen[:count]


def embedder() -> LsaEmbeddings:
    """Load the fitted model, or fit one on the whole corpus if none exists yet.

    Fitting on the whole corpus rather than on the three seeds is deliberate: a model
    fitted on three documents would have a vocabulary too small to behave like the one the
    evaluation measured.
    """
    if DEFAULT_LSA_ARTIFACT.exists():
        return LsaEmbeddings.load(DEFAULT_LSA_ARTIFACT)
    texts: list[str] = []
    for path in sorted(CORPUS.glob("*.txt")):
        parsed = parse_text(path.read_text(encoding="utf-8"), path.name)
        texts.extend(chunk.text for chunk in chunk_document(parsed, "recursive-512"))
    model = LsaEmbeddings().fit(texts)
    model.save(DEFAULT_LSA_ARTIFACT)
    return model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()

    settings = get_settings()
    paths = pick(args.count)
    if not paths:
        print("no corpus documents found; nothing to seed")
        return 1

    model = embedder()
    seeded: list[dict[str, object]] = []
    with session_scope() as session:
        for path in paths:
            parsed = parse_text(path.read_text(encoding="utf-8"), f"{path.stem}.txt")
            result = index_parsed_document(
                session,
                parsed,
                embedder=model,
                chunk_strategy=settings.chunk_strategy,
                index_name=settings.chunk_strategy,
                byte_size=path.stat().st_size,
                meta={"seed": "true", "corpus": "cuad-supply-chain-subset"},
            )
            seeded.append(
                {
                    "document_id": str(result.document_id),
                    "filename": parsed.filename,
                    "pages": result.page_count,
                    "chunks": result.chunk_count,
                    "clauses": result.clause_count,
                    "deduplicated": result.deduplicated,
                }
            )

    print(json.dumps({"seeded": seeded, "embedding_provider": model.name}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
