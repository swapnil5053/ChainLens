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
Chunking fixed at `clause-aware`, retrieval scoped to one document.

| retrieval | Recall@3 | Recall@6 | Recall@10 | MRR | p50 ms |
|---|---|---|---|---|---|
| dense (pgvector cosine) | 0.565 | 0.673 | 0.728 | 0.604 | 81.8 |
| MMR (lambda 0.5) | 0.395 | 0.475 | 0.587 | 0.573 | 82.3 |
| lexical (Postgres FTS, ts_rank_cd) | 0.489 | 0.663 | 0.726 | 0.528 | 1.7 |
| RRF fusion (dense + lexical, k=60) | 0.582 | 0.677 | 0.756 | 0.601 | 81.1 |
| RRF fusion + glossary query expansion | 0.586 | 0.690 | 0.770 | 0.624 | 81.2 |
| RRF fusion + cross-encoder rerank | -- | -- | -- | -- | -- |
Cells marked `--` were not measured:
- cross-encoder weights could not be loaded (3 configurations)
<!-- eval:headline:end -->

## Full ablation grid

<!-- eval:full:start -->
| chunking | retrieval | Recall@3 | Recall@6 | Recall@10 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| `recursive-512` | dense (pgvector cosine) | 0.383 | 0.498 | 0.570 | 0.547 | 0.489 | 79.6 | 85.5 |
| `recursive-512` | MMR (lambda 0.5) | 0.232 | 0.279 | 0.356 | 0.519 | 0.327 | 86.3 | 100.5 |
| `recursive-512` | lexical (Postgres FTS, ts_rank_cd) | 0.316 | 0.474 | 0.554 | 0.494 | 0.441 | 1.9 | 2.9 |
| `recursive-512` | RRF fusion (dense + lexical, k=60) | 0.381 | 0.519 | 0.604 | 0.556 | 0.501 | 81.7 | 95.4 |
| `recursive-512` | RRF fusion + glossary query expansion | 0.401 | 0.551 | 0.625 | 0.596 | 0.535 | 82.8 | 91.4 |
| `recursive-512` | RRF fusion + cross-encoder rerank | -- | -- | -- | -- | -- | -- | -- |
| `recursive-1024` | dense (pgvector cosine) | 0.498 | 0.631 | 0.713 | 0.556 | 0.566 | 80.5 | 84.2 |
| `recursive-1024` | MMR (lambda 0.5) | 0.388 | 0.425 | 0.526 | 0.526 | 0.440 | 83.3 | 85.3 |
| `recursive-1024` | lexical (Postgres FTS, ts_rank_cd) | 0.428 | 0.603 | 0.681 | 0.500 | 0.506 | 1.7 | 2.5 |
| `recursive-1024` | RRF fusion (dense + lexical, k=60) | 0.507 | 0.638 | 0.738 | 0.566 | 0.573 | 84.1 | 87.2 |
| `recursive-1024` | RRF fusion + glossary query expansion | 0.534 | 0.659 | 0.760 | 0.617 | 0.614 | 82.4 | 86.6 |
| `recursive-1024` | RRF fusion + cross-encoder rerank | -- | -- | -- | -- | -- | -- | -- |
| `clause-aware` | dense (pgvector cosine) | 0.565 | 0.673 | 0.728 | 0.604 | 0.601 | 81.8 | 89.7 |
| `clause-aware` | MMR (lambda 0.5) | 0.395 | 0.475 | 0.587 | 0.573 | 0.486 | 82.3 | 85.5 |
| `clause-aware` | lexical (Postgres FTS, ts_rank_cd) | 0.489 | 0.663 | 0.726 | 0.528 | 0.546 | 1.7 | 2.4 |
| `clause-aware` | RRF fusion (dense + lexical, k=60) | 0.582 | 0.677 | 0.756 | 0.601 | 0.614 | 81.1 | 85.9 |
| `clause-aware` | RRF fusion + glossary query expansion | 0.586 | 0.690 | 0.770 | 0.624 | 0.629 | 81.2 | 86.3 |
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
| dense (pgvector cosine) | 81.8 | 79.2 | 2.6 | 89.7 |
| MMR (lambda 0.5) | 82.3 | 76.9 | 4.9 | 85.5 |
| lexical (Postgres FTS, ts_rank_cd) | 1.7 | 0.0 | 1.7 | 2.4 |
| RRF fusion (dense + lexical, k=60) | 81.1 | 76.2 | 4.6 | 85.9 |
| RRF fusion + glossary query expansion | 81.2 | 76.2 | 4.8 | 86.3 |
| RRF fusion + cross-encoder rerank | -- | -- | -- | -- |
Cells marked `--` were not measured:
- cross-encoder weights could not be loaded (3 configurations)
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
Generated by `python -m eval.report` from 19 files in `eval/results/`. Runs produced at commit `b48878f962e7` (working tree dirty at run time) on 2026-08-02T08:14:54+00:00.

Dataset `eval/datasets/golden.jsonl`, sha256 `4ac8d01460a836c4`, 110 questions across 29 documents and 20 clause categories. Embedding provider `lsa-tfidf-svd-384` (dim 384); Postgres 16.2.

The embedding provider is not `bge-small-en-v1.5`: the model hub was unreachable in the environment these numbers were produced in, so a corpus-fitted LSA model was used instead. Absolute values are a floor for the architecture, not a claim about a modern encoder.
<!-- eval:provenance:end -->

## Structured extraction

Thirteen commercial fields, each carrying a character span. A value whose span cannot be
located in the source is dropped rather than emitted, so every extracted value can be
pointed at. Ten risk rules run over the result from a committed YAML file.

Measured against 137 CUAD lawyer annotations across all 29 documents: micro precision
0.722, recall 0.588, F1 0.648, from `eval/results/extraction__cuad.json`, regenerated by
`python -m eval.run_extraction`.

Extraction is pattern-based rather than model-based. That is a real compromise: it is
predictable and cheap and it cannot hallucinate a value, but it recovers only what the
patterns anticipate, and the recall figure shows it.

Three things put a floor under that score, named in the result file as
`known_mismatches` rather than omitted from it:

1. `penalty_per_day` scores zero, and most of that is a mapping artifact. CUAD's
   "Liquidated Damages" category annotates termination fees and cancellation charges
   generally, while this field is specifically a per-day rate. Most annotated clauses in
   this corpus contain no per-day figure at all.
2. Eight of the 29 documents redact commercial figures as `[***]`. A numeric liability cap
   is not present in the source for those, so no extractor could recover one. The
   qualitative limitation is emitted instead, and the `liability-cap-language-only` rule
   flags that it is language rather than a number.
3. "Warranty Duration" annotations frequently mark a clause that states no duration, for
   example one incorporating a standard warranty by reference. Those are unrecoverable as
   a number.

Six fields have no CUAD equivalent and are reported as unlabelled rather than scored
against a proxy: `incoterm`, `delivery_sla_hours`, `penalty_cap`, `jurisdiction`,
`payment_terms_days`, `force_majeure_events`.

The most useful single output is not a field but a rule. `liability-cap-language-only`
fires on 25 of the 29 agreements, meaning almost every contract in this corpus limits
liability in words rather than in a figure. A portfolio-level exposure question cannot be
answered from these documents without reading them.
