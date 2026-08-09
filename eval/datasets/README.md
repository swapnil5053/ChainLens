# The golden set: provenance, licence, and labelling protocol

## Source

**CUAD v1** (Contract Understanding Atticus Dataset), published by The Atticus Project.
510 commercial contracts with 13,000+ clause annotations produced by qualified lawyers.

- Licence: **CC BY 4.0**. Attribution: The Atticus Project, CUAD v1.
- Obtained by cloning `https://github.com/TheAtticusProject/cuad` and reading
  `data/CUADv1.json`. The clone is not committed; the derived subset is.
- Paper: Hendrycks, Burns, Chen, Ball, "CUAD: An Expert-Annotated NLP Dataset for Legal
  Contract Review", NeurIPS 2021 Datasets and Benchmarks.

## What is committed here

| Path | Contents |
|---|---|
| `corpus/*.txt` | Full text of the 29 selected contracts, redistributed under CC BY 4.0. |
| `golden.jsonl` | 110 question / answer-span records. |
| `questions.yaml` | The committed question template for each clause category. |
| `build_golden.py` | The script that regenerates both from CUAD. |

Regenerate with:

```
python -m eval.datasets.build_golden --cuad var/cuad/data/CUADv1.json
```

The build is deterministic: fixed seed, fixed selection rules, sorted output.

## Selection rules

**Documents.** A CUAD contract is eligible when its title contains one of DISTRIBUTOR,
DISTRIBUTION, SUPPLY, MANUFACTURING, MANUFACTURE, TRANSPORTATION, LOGISTICS, RESELLER,
OUTSOURCING, STRATEGIC ALLIANCE or SERVICE; its text is between 20,000 and 90,000
characters; and it carries at least four answerable annotations in the categories below.
Eligible contracts are ranked by annotation density and 29 are taken.

**Categories.** 20 of CUAD's 41 categories, restricted to the ones a supply-chain or
procurement reviewer acts on: liability caps and uncapped liability, insurance, warranty
duration, renewal and notice periods, termination for convenience, minimum commitments,
volume and price restrictions, liquidated damages, audit rights, anti-assignment,
exclusivity, post-termination obligations, revenue sharing, governing law, effective and
expiration dates, and parties. Categories about IP escrow, licensing grants and employee
solicitation are excluded as out of scope.

**Balancing.** Pairs are taken round-robin across categories, so no single clause type
dominates the aggregate metric.

## The human / generated split, stated precisely

This matters and is easy to blur, so it is written out per field.

| Field | Origin |
|---|---|
| Contract text | Human-authored commercial contract, filed with the SEC, redistributed by CUAD. |
| Answer spans | **Human-labelled.** Lawyer annotations from CUAD, unmodified. |
| Question wording | **Generated** from a committed per-category template in `questions.yaml`. |
| Relevance judgements | **Derived**, mechanically, from the human answer spans and the chunk offsets. |

So: 110 of 110 pairs have human-labelled answers, and 110 of 110 have generated question
wording. There are no synthetic contracts and no model-generated answers in this set.

**Why the questions are not CUAD's own.** CUAD ships one prompt per category, of the
form *"Highlight the parts (if any) of this contract related to 'Cap On Liability' that
should be reviewed by a lawyer. Details: ..."*. That is an annotation instruction. It
names the category explicitly, so retrieval scored against it partly measures how well a
retriever matches a category name to a heading. The templates here are what an analyst
would type. The original CUAD prompt is retained in each record as `cuad_question`, so
the alternative framing can be measured later.

## Verification

Every pair is verified before it is written: the annotated answer text must be locatable
in the normalised document text, first at the annotated offset, then by exact search,
then by a whitespace-tolerant search. **A pair whose answer span cannot be located is
discarded, not approximated.** The build reports the discard count; in the committed
build it is 0 of 382 candidate annotations considered.

## Known limitations

1. **Document-scoped retrieval.** Each question is evaluated against its own contract.
   The harder cross-document setting is not measured, and these numbers must not be
   quoted as if it were.
2. **Category coverage is uneven across documents.** Not every contract carries every
   clause type, which is a property of real contracts rather than of the sampling.
3. **CUAD text is OCR-derived** and its heading structure is irregular, which suppresses
   clause detection: 417 of 1,509 clause-aware chunks carry a detected clause id. Cleanly
   typeset contracts detect far better, so the clause-aware numbers here are conservative.
4. **No generation-side labels.** The set scores retrieval. Groundedness and answer
   correctness need a judge model, which was unavailable.
