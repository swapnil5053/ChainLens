# Structured extraction, risk rules, and comparison

Every number in this file comes from `eval/results/extraction__cuad.json`. Regenerate it
with `python -m eval.run_extraction`, which needs no database and no network.

## What is extracted

Thirteen fields, defined in `apps/api/chainlens/extraction/schema.py`. Each carries its
value, a confidence heuristic, the page, the character span, the clause id where one was
detected, and the exact evidence string the value was read from.

**A field whose span cannot be located in the document is dropped, not emitted.** That is
the single rule that makes the output auditable: there is no value on screen that a reader
cannot click through to.

## How it is extracted, and why that is a compromise

Deterministically, with patterns. The brief asks for schema-constrained extraction; a
language model was not available in this environment, and a model whose output cannot be
checked against the source is precisely the failure this project exists to avoid. Patterns
over contract language are crude and will miss unusual phrasing. What they are is
verifiable, and their accuracy is measured below rather than asserted.

A model-backed extractor implements the same interface and its candidates would pass
through the same `verify_span` gate. That gate, not the extractor, is the part that
matters.

## Measured accuracy

Ground truth is CUAD's lawyer annotations over all 29 corpus documents: 137 labelled
(document, field) pairs, built by `python -m eval.datasets.build_extraction_labels` and
committed to `eval/datasets/extraction_labels.jsonl`. Nothing was hand-labelled by the
author, which is the point.

Scoring:

- **true positive** the field was emitted and its span overlaps a human-annotated span
- **false positive** the field was emitted at the wrong span, or in a document where the
  annotators recorded no such clause
- **false negative** an annotation exists and nothing was emitted

Span overlap rather than string equality is deliberate. The extractor reads "thirty (30)
days prior written notice" and returns `30`; the annotator highlighted the sentence.
Requiring those to be string-equal would measure formatting, not extraction.

### Result, current

| field | precision | recall | F1 | tp | fp | fn |
|---|---|---|---|---|---|---|
| governing_law | 1.000 | 0.690 | 0.816 | 20 | 0 | 9 |
| insurance_required | 1.000 | 0.684 | 0.812 | 13 | 0 | 6 |
| liability_cap | 0.615 | 0.941 | 0.744 | 16 | 10 | 1 |
| auto_renew | 0.917 | 0.478 | 0.629 | 11 | 1 | 12 |
| warranty_period_months | 0.714 | 0.294 | 0.417 | 5 | 2 | 12 |
| termination_notice_days | 0.263 | 0.625 | 0.370 | 5 | 14 | 3 |
| penalty_per_day | 0.000 | 0.000 | 0.000 | 0 | 0 | 6 |

**Micro precision 0.722, recall 0.588, F1 0.648. Macro precision 0.644, recall 0.530.**

### The first pass, and a caveat about it

The first version of these patterns scored **micro precision 0.833, recall 0.385, F1
0.526**. Broadening the liability, notice-period and warranty patterns raised recall to
0.588 and F1 to 0.648, at the cost of eleven points of precision.

**Those first-pass figures are not reproducible from this tree.** They came from a run
whose artifact was overwritten when the improved extractors replaced it, and the patterns
that produced them no longer exist in the source. They are reported here because the
direction of the trade is the point, but they do not meet the standard every other number
in this repository meets, and they should be read as a note rather than as evidence. Only
`eval/results/extraction__cuad.json` is regenerable.

The trade itself is the interesting part: for a review tool
that shows its evidence, a false positive costs a reader one glance at a span, while a
false negative costs them a clause they never saw. That asymmetry is why the trade was
taken, and it is a judgement rather than a fact.

### Three things that put a floor under this score

Named in the result file as `known_mismatches`, not omitted from it.

1. **`penalty_per_day` scores zero, and most of that is a mapping artifact.** CUAD's
   "Liquidated Damages" category annotates termination fees and cancellation charges
   generally; this field is specifically a per-day rate. Most annotated clauses in this
   corpus contain no per-day figure at all.
2. **Eight of the 29 documents redact commercial figures as `[***]`.** A numeric liability
   cap is not present in the source for those, so no extractor could recover one. The
   qualitative limitation is emitted instead, and the `liability-cap-language-only` rule
   flags that it is not a number.
3. **"Warranty Duration" annotations frequently mark a clause that states no duration**,
   for example one incorporating a standard warranty by reference. Those are unrecoverable
   as a number.

Six fields have no CUAD equivalent and are reported as unlabelled rather than scored
against a proxy: `incoterm`, `delivery_sla_hours`, `penalty_cap`, `jurisdiction`,
`payment_terms_days`, `force_majeure_events`.

## Risk rules

Ten rules in `apps/api/chainlens/extraction/risk_rules.yaml`. Data, not code, so adding one
is a one-line diff a procurement lead can argue with and no deploy. The `when` expression
language supports `present`, `absent`, `equals`, `lt`, `lte`, `gt`, `gte`, `matches`,
`same_place`, `all`, `any` and `not`, and is evaluated by a small interpreter rather than
`eval`, because a rules file is the kind of thing that gets edited by someone who is not
reading the Python.

Every flag carries the span of the first field it names that was extracted, so a flag links
to the sentence that caused it.

Fired across the 29-document corpus:

| rule | documents |
|---|---|
| liability-cap-language-only | 25 |
| no-insurance-obligation | 16 |
| force-majeure-no-epidemic | 13 |
| missing-force-majeure | 11 |
| jurisdiction-mismatch | 6 |
| uncapped-liability | 3 |
| auto-renew-notice-unknown | 3 |
| auto-renew-short-notice | 2 |

That `liability-cap-language-only` fires on 25 of 29 is the most useful thing on this page:
almost every agreement in this corpus limits liability in words rather than in a figure,
which means a portfolio-level "what is our total exposure" question cannot be answered from
these contracts at all without reading them.

## Comparison

`POST /compare` diffs two extractions field by field, with per-field status `same`,
`differs`, `missing_left` or `missing_right`. Lists compare as sorted sets, so a force
majeure clause listing the same events in a different order is the same. Strings compare
case-insensitively with whitespace collapsed, because contract text is full of line breaks
that carry no meaning. Nothing else is coerced: `30` and `"thirty days"` stay different
until an extractor makes them the same, which is the extractor's job and not the diff's.

## Endpoints

| Method | Path | Returns |
|---|---|---|
| POST | `/documents/{id}/extract` | `ContractExtraction`, with `fields` and an explicit `missing` list |
| GET | `/documents/{id}/risk` | `RiskReport`, flags sorted by severity |
| POST | `/compare` | `CompareReport`, one row per field present on either side |
