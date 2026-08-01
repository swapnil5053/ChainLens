# ChainLens v2 rebuild plan

Written at the start of the autonomous session, before any code changed. Status of each
item is tracked in `docs/PROGRESS.md`; blockers in `docs/HANDOFF.md`.

## Environment reality check, probed first, decisions follow from it

| Capability | Result | Consequence |
|---|---|---|
| Docker / docker compose | not installed, no root, no apt | Compose files are authored but cannot be executed here. Phase 1 acceptance is verified against a locally started Postgres instead. |
| PostgreSQL 16 + pgvector | AVAILABLE via `pgserver` (PyPI, bundles PG 16.2 and pgvector 0.6.2) | The locked storage decision is kept. No substitution. |
| Redis | no server binary, no root to install one | `arq` job code is written; the worker is not exercised end to end. Ingestion runs inline. |
| huggingface.co | blocked by the egress proxy on every host (`HTTP 403 from proxy after CONNECT`) | `bge-small-en-v1.5` and `bge-reranker-base` weights unobtainable. See ADR-0003 and ADR-0004. |
| generativelanguage.googleapis.com | blocked, and no API key present | Gemini generation and embeddings cannot run. Generation-side eval is BLOCKED, not estimated. |
| github.com over https | reachable | CUAD is obtainable by `git clone`, so the golden set is built from real human annotations. |
| pypi.org, registry.npmjs.org | reachable | Python and Node dependency installs work. |

## Order of work

Priority order is taken from section 8 of the brief, not the phase numbering.

1. Phase 1 foundations, because everything else needs the package layout and the DB.
2. Phase 2 ingestion with character offsets, because the eval and the citation UI both
   depend on them.
3. Phase 3 evaluation harness, the spine.
4. Phase 4 retrieval work, each step measured against phase 3.
5. Frontend taste pass and the Analyse screen.
6. Phase 5 extraction, compare, risk.
7. Phases 6 to 8 as time allows.

## Evidence discipline

Every number in any committed document comes from a file in `eval/results/`.
`python -m eval.report` regenerates the tables in `README.md` and `docs/RETRIEVAL.md`
from those files. Anything not measured is written as a dash with a footnote, never as a
plausible-looking figure.
