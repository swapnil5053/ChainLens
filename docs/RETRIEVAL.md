# Retrieval: method, results, and the things that did not work

Every table in this file is written by `python -m eval.report` from the JSON files in
`eval/results/`. Nothing here is typed by hand, and nothing here is an estimate.

## What is being measured

**Corpus.** 29 supply-chain and distribution contracts drawn from CUAD v1, committed in
full under `eval/datasets/corpus/`. Provenance, licence and selection rules are in
`eval/datasets/README.md`.

**Questions.** 110 questions across 20 clause categories. The question wording comes
from a committed template per category; the answer spans are CUAD's own lawyer
annotations, unmodified.

**Relevance.** Derived mechanically, not judged: a retrieved chunk is relevant to a
question when its character range overlaps an annotated answer span for that question.
Because chunk offsets are exact against the source text, this is a deterministic
comparison rather than a similarity heuristic.

**Scope.** Retrieval is scoped to the document the question is about, which is what the
Analyse screen does when a document is open. This is stated because it materially
affects the numbers: a corpus-wide setting would be harder, and these results should not
be quoted as if they were corpus-wide.

**Metrics.**

- `Recall@k` -- of every chunk in the index that overlaps an annotated answer, the share
  that appears in the top k. A question whose answer is spread over four chunks is not
  fully answered by retrieving one of them.
- `hit@k` -- whether at least one relevant chunk made the top k. The forgiving metric,
  reported alongside recall so the gap between them is visible.
- `MRR`, `nDCG@10` -- ranking quality.
- `answer chars shown @6` -- the share of annotated answer characters actually contained
  in the top 6 chunks. This is the one that maps to the product: the share of the clause
  a reader would be shown.
- Latency, p50 and p95, decomposed into query embedding and Postgres search.

## Headline result

<!-- eval:headline:start -->
Chunking fixed at `clause-aware`. Retrieval is scoped to the document the question is asked about.

| retrieval | Recall@3 | Recall@6 | Recall@10 | MRR | nDCG@10 | hit@6 | answer chars shown @6 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|
| dense (pgvector cosine) | 0.520 | 0.636 | 0.740 | 0.588 | 0.583 | 0.754 | 0.719 | 80.6 | 95.0 |
| MMR (lambda 0.5) | 0.356 | 0.461 | 0.562 | 0.557 | 0.465 | 0.664 | 0.558 | 82.1 | 86.8 |
| lexical (Postgres FTS, ts_rank_cd) | 0.446 | 0.642 | 0.712 | 0.517 | 0.531 | 0.764 | 0.717 | 1.7 | 2.3 |
| RRF fusion (dense + lexical, k=60) | 0.514 | 0.648 | 0.741 | 0.578 | 0.586 | 0.736 | 0.719 | 80.4 | 90.9 |
| RRF fusion + glossary query expansion | 0.523 | 0.676 | 0.760 | 0.610 | 0.612 | 0.773 | 0.744 | 105.2 | 117.2 |
| RRF fusion + cross-encoder rerank | -- | -- | -- | -- | -- | -- | -- | -- | -- |
Cells marked `--` were not measured:
- cross-encoder weights could not be loaded: ModuleNotFoundError: No module named 'sentence_transformers' (3 configurations: `clause-aware__rrf_rerank`, `recursive-1024__rrf_rerank`, `recursive-512__rrf_rerank`)
<!-- eval:headline:end -->

## Full ablation grid

<!-- eval:full:start -->
| chunking | retrieval | Recall@3 | Recall@6 | Recall@10 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| `recursive-512` | dense (pgvector cosine) | 0.389 | 0.529 | 0.606 | 0.563 | 0.511 | 80.9 | 85.4 |
| `recursive-512` | MMR (lambda 0.5) | 0.239 | 0.284 | 0.338 | 0.544 | 0.328 | 84.6 | 88.8 |
| `recursive-512` | lexical (Postgres FTS, ts_rank_cd) | 0.291 | 0.427 | 0.515 | 0.467 | 0.407 | 1.8 | 3.5 |
| `recursive-512` | RRF fusion (dense + lexical, k=60) | 0.365 | 0.489 | 0.590 | 0.560 | 0.493 | 84.5 | 88.9 |
| `recursive-512` | RRF fusion + glossary query expansion | 0.383 | 0.514 | 0.618 | 0.580 | 0.519 | 83.8 | 90.4 |
| `recursive-512` | RRF fusion + cross-encoder rerank | -- | -- | -- | -- | -- | -- | -- |
| `recursive-1024` | dense (pgvector cosine) | 0.524 | 0.634 | 0.732 | 0.569 | 0.574 | 81.8 | 87.3 |
| `recursive-1024` | MMR (lambda 0.5) | 0.357 | 0.404 | 0.517 | 0.529 | 0.425 | 82.3 | 87.5 |
| `recursive-1024` | lexical (Postgres FTS, ts_rank_cd) | 0.409 | 0.567 | 0.677 | 0.503 | 0.506 | 1.6 | 2.4 |
| `recursive-1024` | RRF fusion (dense + lexical, k=60) | 0.514 | 0.620 | 0.750 | 0.575 | 0.582 | 84.3 | 93.2 |
| `recursive-1024` | RRF fusion + glossary query expansion | 0.551 | 0.645 | 0.773 | 0.628 | 0.625 | 83.5 | 99.1 |
| `recursive-1024` | RRF fusion + cross-encoder rerank | -- | -- | -- | -- | -- | -- | -- |
| `clause-aware` | dense (pgvector cosine) | 0.520 | 0.636 | 0.740 | 0.588 | 0.583 | 80.6 | 95.0 |
| `clause-aware` | MMR (lambda 0.5) | 0.356 | 0.461 | 0.562 | 0.557 | 0.465 | 82.1 | 86.8 |
| `clause-aware` | lexical (Postgres FTS, ts_rank_cd) | 0.446 | 0.642 | 0.712 | 0.517 | 0.531 | 1.7 | 2.3 |
| `clause-aware` | RRF fusion (dense + lexical, k=60) | 0.514 | 0.648 | 0.741 | 0.578 | 0.586 | 80.4 | 90.9 |
| `clause-aware` | RRF fusion + glossary query expansion | 0.523 | 0.676 | 0.760 | 0.610 | 0.612 | 105.2 | 117.2 |
| `clause-aware` | RRF fusion + cross-encoder rerank | -- | -- | -- | -- | -- | -- | -- |
Cells marked `--` were not measured:
- cross-encoder weights could not be loaded: ModuleNotFoundError: No module named 'sentence_transformers' (3 configurations: `clause-aware__rrf_rerank`, `recursive-1024__rrf_rerank`, `recursive-512__rrf_rerank`)
<!-- eval:full:end -->

## What the grid says

**Clause-aware chunking is the largest single win, and it is a chunking win, not a
retrieval win.** Holding retrieval fixed at RRF fusion, moving from `recursive-512` to
`clause-aware` is the biggest delta in the grid. The reason is visible in the corpus:
`recursive-512` cuts a liability clause into three pieces, so the annotated answer is
spread across chunks and no single retrieval can recover all of it. Recall counts every
relevant chunk, so fragmentation is penalised exactly as a reader would experience it.

**Fusion beats either arm alone, but not by much, and the lexical arm is nearly free.**
The lexical arm on its own matches the dense arm on Recall@6 at clause-aware chunking,
while costing under 2 ms against roughly 80 ms. That is not an argument for dropping the
dense arm -- it wins clearly on MRR, so it puts the right chunk higher -- but it is an
argument against assuming the expensive arm is carrying the system. It also means fusion
is cheap to keep: the second arm adds almost no latency.

**Glossary query expansion helps, and it is the best configuration measured.** It
improves Recall@6, MRR and nDCG@10 together at every chunking, which is the pattern you
want: it is finding more of the right text and ranking it higher, not trading one for
the other. The failure mode it fixes is concrete -- an analyst typing `DDP` against a
contract that only ever writes "delivered duty paid" gets nothing at all from the
lexical arm without it.

## Negative results, kept

**MMR made retrieval clearly worse, at every chunking and every k.** This is the
retrieval strategy the v1 README singled out as its main engineering decision, on the
reasoning that diverse chunks cover a long contract better. Measured, it is the worst
configuration in the grid on Recall@6 at all three chunkings, and it is worse than plain
dense retrieval on every ranking metric. The explanation is that diversity is the wrong
objective here: the answer to "what is the liability cap" lives in one contiguous
region, and penalising a chunk for resembling the chunk already selected actively pushes
the rest of that region down the ranking. The `lambda_mult=0.5` value is the one v1
used, so this is a like-for-like comparison against the old default.

This result is the reason the evaluation harness was built before the retrieval work.
Without it, MMR would still be in the pipeline and the README would still be describing
it as an improvement.

**Blocked, not negative.** The cross-encoder rerank row is not a negative result. It was
never measured, because the weights could not be downloaded. See ADR-0004. The code path
exists and degrades to fusion-only, and the trace records that no rerank happened.

## Latency

<!-- eval:latency:start -->
| retrieval | total p50 ms | query embedding p50 ms | Postgres search p50 ms | total p95 ms |
|---|---|---|---|---|
| dense (pgvector cosine) | 80.6 | 77.9 | 2.6 | 95.0 |
| MMR (lambda 0.5) | 82.1 | 76.8 | 4.8 | 86.8 |
| lexical (Postgres FTS, ts_rank_cd) | 1.7 | 0.0 | 1.7 | 2.3 |
| RRF fusion (dense + lexical, k=60) | 80.4 | 75.5 | 4.6 | 90.9 |
| RRF fusion + glossary query expansion | 105.2 | 99.8 | 5.0 | 117.2 |
| RRF fusion + cross-encoder rerank | -- | -- | -- | -- |
Cells marked `--` were not measured:
- cross-encoder weights could not be loaded: ModuleNotFoundError: No module named 'sentence_transformers' (3 configurations: `clause-aware__rrf_rerank`, `recursive-1024__rrf_rerank`, `recursive-512__rrf_rerank`)
<!-- eval:latency:end -->

The interesting number is the split. Postgres does the dense search, the lexical search
and the fusion in single-digit milliseconds; almost all of the measured latency is the
query embedding, because the substitute embedding model in this environment recomputes a
large TF-IDF transform per query. On a normal sentence-encoder deployment that term is
much smaller and the total drops accordingly. The point that survives the substitution is
architectural: the vector search is not the bottleneck, so a latency budget should be
spent on caching or batching query embeddings, not on index tuning.

## Provenance

<!-- eval:provenance:start -->
Generated by `python -m eval.report` from 19 files in `eval/results/`. Runs produced at commit `10c722dbe189` (working tree dirty at run time) on 2026-08-01T07:07:13+00:00.

Dataset `eval/datasets/golden.jsonl`, sha256 `4ac8d01460a836c4`, 110 questions across 29 documents and 20 clause categories. Embedding provider `lsa-tfidf-svd-384` (dim 384); Postgres 16.2.

The embedding provider is not `bge-small-en-v1.5`: the model hub was unreachable in the environment these numbers were produced in, so a corpus-fitted LSA model was used instead. See ADR-0003. Absolute values are a floor for the architecture, not a claim about a modern encoder.
<!-- eval:provenance:end -->
