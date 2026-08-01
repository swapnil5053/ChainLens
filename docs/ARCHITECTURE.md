# Architecture

## Shape

```
apps/api/chainlens/
  config.py        every tunable, one place, environment-driven
  paths.py         all filesystem anchors resolve from the repository root
  logging.py       structured JSON logging with a request id in every record
  ingest/          parse with offsets, clause-aware chunking, SHA-256, state machine
  embeddings/      the provider interface and its four implementations
  retrieval/       dense arm, lexical arm, RRF fusion, reranker, query expansion
  generation/      prompt, streaming client with a real timeout, groundedness guard
  extraction/      reserved for Phase 5, not implemented in this session
  db/              SQLAlchemy models and session management
  api/             routers and request or response schemas
  jobs/            arq worker
eval/              golden set, runners, ablation sweep, report generator, CI gate
apps/web/          token layer and the Evaluation screen prototype
infra/             Dockerfiles and the compose stack
```

## The two interfaces that make the rest replaceable

**`EmbeddingProvider`** (`embeddings/base.py`) has four members: `name`, `dim`,
`embed_documents`, `embed_query`. Nothing downstream of it knows which implementation is
in use. There are four: `LsaEmbeddings` fitted on the corpus with no network,
`SentenceTransformerEmbeddings` for `bge-small-en-v1.5`, `GeminiEmbeddings` over plain
HTTP with an explicit timeout, and `StubEmbeddings` for unit tests. The provider name is
written into every embedding row and every evaluation result, so a result can never be
misattributed to a provider that did not produce it, and the eval runner refuses to write
metrics produced by the stub.

**`Reranker`** (`retrieval/rerank.py`) has an `available` property alongside `rerank`.
That property is the whole design: a reranker is a hard dependency on model weights that
may not be there, so the pipeline asks before it calls and records the answer in the
trace. When weights are missing, retrieval keeps fusion order, the trace says
`reranker_available: false`, and the SSE phase event for reranking carries a note
explaining it. Nothing in the system can report a rerank that did not happen.

## Data model

Six tables, in `apps/api/alembic/versions/0001_baseline.py`.

| Table | Holds | Notable columns |
|---|---|---|
| `documents` | one row per unique content hash | `sha256` unique, `full_text`, `pages` as JSONB page boundaries |
| `chunks` | one row per chunk per index | `char_start`, `char_end`, `page_spans`, `clause_id`, and a generated `search_vector` |
| `embeddings` | one vector per chunk per provider | `vector(384)` with an HNSW cosine index |
| `jobs` | ingest state machine | `state`, `progress`, `timings_ms` |
| `queries` | one row per answered question | retrieval, rerank and generation milliseconds, tokens, cost, config hash |
| `eval_runs` | evaluation runs, mirroring the JSON artifacts | `config`, `metrics`, `status` |

Two choices worth defending.

`chunks.search_vector` is a Postgres **generated column**, `to_tsvector('english', text)`
stored, with a GIN index. A generated column cannot drift from the text it indexes,
because the database computes it. The alternative, maintaining it in application code or a
trigger, has a failure mode where a chunk is updated and its lexical index silently is
not.

`chunks` carries `index_name`, so several chunking strategies coexist over the same
documents. That is what makes the chunking ablation an honest comparison: all three
strategies index identical source text with an identical embedding model, and the only
thing that varies is where the boundaries fall.

## Offsets, which everything else depends on

The parser records, for each page, its text and its character range within the assembled
document. Chunking preserves those ranges and additionally computes `page_spans`, the
chunk's footprint on each page it touches, in page-local coordinates.

Two invariants hold for every chunk, and both are asserted in `test_offsets.py` for all
three chunking strategies:

```
document.full_text[chunk.char_start:chunk.char_end] == chunk.text
"\n\n".join(pages[s.page - 1].text[s.start:s.end] for s in chunk.page_spans) == chunk.text
```

The second is the one the interface needs. A citation that can only say "page 14" is a
page reference; a citation that can say "characters 1,204 to 1,559 of page 14" can be
marked on the text. The evaluation harness leans on the same offsets: relevance is
computed by intersecting chunk ranges with CUAD's annotated answer spans, which makes
relevance a deterministic comparison rather than a similarity judgement.

## Retrieval

One query embedding per question, and one SQL statement per arm. The v1 pipeline issued
two identical retrievals per question because an unused key in an LCEL chain requested
the documents a second time. The trace here records `embed_ms`, `dense_ms`, `lexical_ms`,
`fusion_ms` and `rerank_ms` separately, so a duplicated search would be visible in every
evaluation artifact rather than invisible in a bill.

Fusion is reciprocal rank fusion at k=60 over the two ranked lists. Rank is list position,
not a score, which is what makes fusing an unbounded cosine similarity with an unbounded
`ts_rank_cd` value meaningful without normalising either.

## Failure behaviour

The service starts and reports honestly when its dependencies are missing, rather than
crashing or claiming health.

| Missing | Behaviour |
|---|---|
| Embedding provider | `/readyz` returns `degraded` with the construction error; `/documents` and `/query` return 503 with that error |
| Redis | ingestion runs inline in the request; `/readyz` says so under `redis_impact` |
| Cross-encoder weights | retrieval keeps fusion order and marks `reranker_available: false` |
| Generation provider | retrieval and citations still return; `answer_status` is `unavailable` with the reason |

`/health` is liveness and deliberately checks nothing external. `/readyz` opens a
connection to Postgres and pings Redis, because a readiness probe that does not touch its
dependencies is a liveness probe with a different name.

## Evaluation harness

`eval/run.py` writes exactly one JSON artifact per grid cell, containing the run id, the
commit SHA and whether the tree was dirty, the dataset hash, the resolved environment
including the embedding provider description and the Postgres version, the full retrieval
configuration and its hash, aggregate metrics, and per-query rows with the ranks that hit
and the measured latency.

`eval/report.py` is the only writer of results tables in the repository. It rewrites
marked regions in `README.md` and `docs/RETRIEVAL.md` and refreshes `eval/baseline.json`.
CI runs the sweep, then `eval/gate.py`, then `eval.report` followed by
`git diff --exit-code`, so a pull request that changes retrieval without regenerating the
tables fails rather than merging with stale numbers.
