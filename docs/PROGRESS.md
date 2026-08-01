# Progress log

One entry per phase. Each entry names the command that proves the claim.

## Phase 1: triage and foundations

Shipped: every defect in section 2 of the brief fixed; the Streamlit application
deleted; the `apps/api` package layout in place; the Alembic baseline applied against
a real PostgreSQL 16 with pgvector; ruff, ruff-format and a no-emoji hook wired.

## Phase 1 defect triage: evidence

Greps run against the v1 tree at commit 10c722d, then against the v2 tree.

### 1. Double retrieval per query

```
$ grep -n "retriever.invoke" app/core/rag_pipeline.py
50:            context=lambda x: retriever.invoke(x["input"]),
51:            _docs=lambda x: retriever.invoke(x["input"])
```

### 2. Timeout that does not cancel

```
$ grep -rn "thread.join\|daemon = True" app/
app/core/rag_pipeline.py:82:        thread.daemon = True
app/core/rag_pipeline.py:84:        thread.join(timeout=30.0)
```

### 3. Path drift between README and code

```
$ grep -rn "vector_store\|Vector_DB" README.md app/
README.md:59:- **Persistent indexing**: The vector store is written to disk under `.vector_store`. Documents are not re-embedded on restart.
app/core/retriever.py:123:    db_path = "Vector_DB - Documents"
app/core/session_state.py:33:            if upload_docs and not os.path.exists("Vector_DB - Documents"):
```

### 4. CWD-relative paths

```
$ grep -rn "makedirs(\"docs\")\|join(\"docs\"\|db_path = " app/
app/core/retriever.py:123:    db_path = "Vector_DB - Documents"
app/core/ingestion.py:17:        pdf_path = os.path.join("docs", pdf)
app/core/ingestion.py:53:        os.makedirs("docs")
app/core/ingestion.py:54:    file_path = os.path.join("docs", uploaded_file.name)
app/core/session_state.py:10:        os.makedirs("docs")
app/app.py:30:            os.makedirs("docs")
```

### 5. No content hashing

```
$ grep -rin "sha256\|hashlib" app/ | wc -l
0
(zero matches: nothing in v1 hashed document content)
```

### 6. Debug scratch committed

```
$ wc -l app/test_debug_hang.py test_app.py
 23 app/test_debug_hang.py
  2 test_app.py
 25 total
```

### 7. Emojis in UI, logs and status strings

```
$ grep -rPc "[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]" app/*.py app/core/*.py
app/app.py:3
app/test_debug_hang.py:0
app/core/__init__.py:0
app/core/ingestion.py:0
app/core/rag_pipeline.py:2
app/core/retriever.py:11
app/core/session_state.py:1
```

### 8. Hardcoded collection name and unbounded metadata scan

```
$ grep -n "name=\"langchain\"\|limit=10000" app/core/retriever.py
136:                existing_collection = client.get_collection(name="langchain")
139:                    items = existing_collection.get(limit=10000)
```

### After: the same greps against the v2 tree

```
$ grep -rn --include="*.py" "thread.join\|daemon = True" apps/ eval/ scripts/
apps/api/chainlens/embeddings/remote.py:9:deliberate: v1 wrapped the call in ``thread.join(timeout=30)``, which returns to the
(one match, in a comment in remote.py explaining why the timeout is now client-level)

$ grep -rn --include="*.py" "Vector_DB\|chromadb\|streamlit\|langchain" apps/ eval/ scripts/; echo "exit=$?"
apps/api/chainlens/config.py:30:        description="Logical index name. v1 hardcoded the string 'langchain'.",
exit=0
(no matches: Chroma, LangChain and Streamlit are gone from the codebase)

$ grep -rn --include="*.py" "os.getcwd\|makedirs(\"docs\")" apps/ eval/ scripts/; echo "exit=$?"
exit=1
(no matches: every path resolves from PROJECT_ROOT in apps/api/chainlens/paths.py)

$ python scripts/check_no_emoji.py; echo "exit=$?"
exit=0

$ grep -c "sha256" apps/api/chainlens/ingest/hashing.py
6

$ grep -n "collection\|metadata_scan_limit" apps/api/chainlens/config.py | head -4
28:    collection: str = Field(
32:    metadata_scan_limit: int = Field(
```

Defect 1 (double retrieval) is structural rather than grep-provable: the pipeline in
`apps/api/chainlens/retrieval/service.py` issues one query embedding and one search
per configured arm, and `RetrievalTrace` records `embed_ms`, `dense_ms` and
`lexical_ms` separately, so a duplicated search would be visible in every eval result.

```
$ CHAINLENS_LOCAL_PG=1 python scripts/migrate.py
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Baseline schema
migrated: postgresql+psycopg://postgres@/postgres?host=<repo>/var/pgdata

$ python -m ruff check . && python -m ruff format --check .
All checks passed!
54 files already formatted
```

## Phase 2: ingestion that respects contract structure

Shipped: PDF and text parsing that retains per-page character offsets; clause-aware
chunking with a recursive fallback; SHA-256 content addressing with a dedupe short
circuit; an explicit ingest state machine.

The acceptance criterion in the brief is an assertion that stored offsets reproduce
the chunk exactly. It is `test_offsets.py`, and it is checked twice per chunk: once
against the document text and once against page-local text via the recorded page
spans, for all three chunking strategies.

```
$ python -m pytest apps/api/tests -q
........................                                                 [100%]
24 passed in 0.59s
```

One test found a bug in a test, not in the code: the first version of
`test_rrf_k_damps_deep_ranks` assumed RRF used the rank recorded on the chunk. It uses
list position, which is correct. The test was rewritten to assert the real contract.

## Phase 3: the evaluation harness

Shipped: a 110-pair golden set built from CUAD with every answer span verified
present, three chunking indexes in Postgres, an 18-cell ablation sweep, and
`python -m eval.report` regenerating every table in the docs from the committed JSON.

```
$ python -m eval.datasets.build_golden
{
  "discarded_unlocatable": 0,
  "considered": 382,
  "kept_pairs": 110,
  "documents": 29,
  "categories": 20
}
```

## Phase 4: retrieval that earns its numbers

Shipped: the Postgres FTS lexical arm, RRF fusion at k=60, glossary query expansion,
and the cross-encoder rerank code path. Results, including the negative MMR result,
are in `docs/RETRIEVAL.md`, every row backed by a file in `eval/results/`.
