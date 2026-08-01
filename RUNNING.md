# Running ChainLens

Three ways to see it, in order of how much setup each needs. The first takes ten seconds.

---

## 0. Before anything: reconcile the folder

This repository was rebuilt in a sandbox that could create files in the connected folder
but not delete them, so the old v1 tree is still sitting next to the new one and git's
index is locked. One checkout clears both.

```bash
cd ChainLens
git fetch chainlens-rebuild-v2.bundle rebuild/v2:rebuild/v2
git checkout rebuild/v2
git clean -fdx -e chainlens-rebuild-v2.bundle
```

If `git checkout` complains about a lock file, delete `.git/index.lock` first. That file is
a leftover from the sandbox and is safe to remove.

After this the tree should contain `apps/`, `eval/`, `docs/`, `infra/`, `scripts/` and no
`app/`, `test_app.py` or `requirements.txt`.

---

## 1. The evaluation screen, no install at all

```
open apps/web/prototype/evaluation.html
```

Double-click it. It is a single self-contained file with the token layer inlined, and it
renders the real committed evaluation artifacts: the 18-cell ablation grid, the headline
Recall@6 of 0.676, and the finding that query embedding is 95 percent of p50 latency. The
theme toggle in the corner switches light and dark, which is the variable swap the token
layer exists to make possible.

Regenerate it after a new eval run with `python scripts/build_eval_prototype.py`.

---

## 2. The three views, Node only, no backend

This is the interface: Analyse, retrieval comparison, and latency. It runs entirely on the
mock adapter, which serves the real 29-contract corpus and computes both retrieval
configurations in your browser. No database, no API key, no Python.

```bash
cd apps/web
npm install        # about 20 seconds, 98 packages
npm run dev        # then open the URL it prints, usually http://localhost:5173
```

What to try, in order:

1. **Pick a contract** from the Corpus list on the right. `Apollo-Endosurgery-Manufacturing-and-Supply-Agreement` is a good first one: 15 pages, plenty of clause structure.
2. **Ask a question.** Click one of the three example questions, or type `What is the cap on liability?` and press Enter.
3. **Click a citation chip.** This is the thing the whole design is built around: the contract pane scrolls to the clause and marks the exact character span, with a rule down the leading edge. Hover a chip first to see the softer preview mark.
4. **Switch to Retrieval comparison.** Same question, two arms. The left is MMR, the strategy this project originally shipped; the right is clause-aware chunking with RRF fusion and glossary expansion. Rows marked `unique` were returned by only one arm. The `Recall@6 delta` at the top is a corpus measurement over 110 lawyer-annotated questions, not a property of the query you just typed, and the panel says so.
5. **Switch to Latency.** The stacked bar is the finding: Postgres does both searches in about 5 ms while the query embedding takes about 100.
6. **Toggle Dark** in the masthead. Every colour is a CSS variable swap; there is not one `dark:` class in the source.

The footer always says `MOCK` and names the adapter. That is deliberate: a demo you cannot
distinguish from live data is the kind that misleads.

Verify it the way CI would:

```bash
npm run verify     # typecheck, then the smoke test, then a production build
```

---

## 3. The backend, Python and a local Postgres, no Docker

```bash
pip install -e ".[dev,localpg]"
make migrate       # starts PostgreSQL 16 with pgvector in-process and applies Alembic
make seed          # indexes three real supply-chain agreements
make demo-local    # serves the API on http://localhost:8000
```

Then, in another shell:

```bash
curl localhost:8000/health
curl localhost:8000/readyz | python -m json.tool     # honest about what is degraded
curl localhost:8000/documents | python -m json.tool

DOC=$(curl -s localhost:8000/documents | python -c "import json,sys;print(json.load(sys.stdin)[0]['id'])")
curl -s -X POST localhost:8000/documents/$DOC/extract | python -m json.tool | head -40
curl -s localhost:8000/documents/$DOC/risk | python -m json.tool
```

`/readyz` will report `degraded` and explain why: no Redis, so ingestion runs inline; no
generation provider, so answers are unavailable while retrieval and citations still work;
no document scoping configured. That is the intended behaviour, not a fault.

### Reproduce every number in the repository

```bash
make index eval    # builds the three chunking indexes, runs the 18-cell ablation
make report        # rewrites every table in README.md and docs/RETRIEVAL.md
make gate          # the CI regression check
make eval-extraction
make check         # lint, types, 40 tests, no-emoji, contrast, glossary parity
```

`make report` followed by `git diff` should show nothing. If it shows a change, the
committed tables were stale, which is exactly what the CI step is there to catch.

---

## What will not work, and why

| | |
|---|---|
| `docker compose up` | Authored but never executed: the build environment had no Docker daemon, no root and no package manager. It is the most likely thing here to be broken on first run. |
| The arq worker | Written, never run. No Redis was installable, so ingestion happens inline in the request. |
| GitHub Actions | The workflow has never executed. |
| Real answers | No generation provider is configured. Retrieval and citations work; the answer text in the mock is extractive, quoting the retrieved clauses verbatim, and it says so under every answer. |
| bge-small embeddings | huggingface.co is blocked from the build environment. The dense arm is a corpus-fitted LSA model instead. See ADR-0003; swapping it is one environment variable. |
