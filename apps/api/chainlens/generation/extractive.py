"""Build an answer by selecting sentences, when no generation model is configured.

Quoting whole retrieved chunks does not read as an answer. A chunk is a retrieval unit: it
begins and ends wherever the chunker cut, it carries page furniture and redaction notices,
and only one or two of its sentences usually bear on the question. Pasting two of them
end to end produces the "fragment salad" this module exists to replace.

So this is query-focused extractive summarisation. Candidate sentences are pulled from the
retrieved chunks, obvious document furniture is discarded, each sentence is scored against
the question with a rarity weighting, and a short set is chosen with a redundancy penalty
so two sentences saying the same thing cannot both be picked. The selection is then
restored to reading order.

It cannot hallucinate: every sentence returned appears verbatim in the contract. That is
the property that makes it an acceptable fallback rather than a stopgap that invents text.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Words carrying no topical signal. Deliberately short: legal text is dense, and stripping
# too much leaves nothing to match on.
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "than",
        "that",
        "this",
        "these",
        "those",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "by",
        "with",
        "without",
        "under",
        "over",
        "into",
        "out",
        "up",
        "down",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "doing",
        "have",
        "has",
        "had",
        "having",
        "it",
        "its",
        "as",
        "such",
        "any",
        "all",
        "each",
        "other",
        "some",
        "no",
        "not",
        "so",
        "nor",
        "only",
        "own",
        "same",
        "very",
        "can",
        "will",
        "just",
        "should",
        "now",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "how",
        "shall",
        "may",
        "must",
        "more",
        "most",
        "per",
        "upon",
        "herein",
        "hereof",
        "hereto",
        "hereunder",
        "thereof",
        "therein",
        "thereto",
        "said",
    ]
)

# Document furniture: redaction notices, confidential-treatment stamps, page markers and
# exhibit headers. These score well on keyword overlap (they are long and repeat contract
# vocabulary) but answer nothing, so they are removed before scoring rather than after.
FURNITURE = re.compile(
    r"""
    (certain\s+confidential\s+information)
    | (confidential\s+treatment)
    | (has\s+been\s+omitted)
    | (omitted\s+(and\s+filed|pursuant))
    | (competitively\s+harmful)
    | (separately\s+filed\s+with\s+the)
    | (securities\s+and\s+exchange\s+commission)
    | (^\s*(page|exhibit|schedule|annex|appendix)\s+[\dixvA-Z]+\s*$)
    | (^\s*[-\u2013\u2014]?\s*\d{1,3}\s*[-\u2013\u2014]?\s*$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Sentence boundary: a terminator followed by whitespace and something that opens a
# sentence -- a capital, a quote, or an enumerated clause heading such as "10.4.2 Each".
_SPLIT = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z(\"'“]|\d+(?:\.\d+)*\s+[A-Z])")

# Abbreviations whose full stop is not a sentence end. Two separate cases, because they
# need different evidence:
#
#   "A. M. Best" - an initialism written with spaces. A trailing single capital is not
#   enough on its own to merge: this corpus is full of "a rating of A." ending a sentence.
#   The tell is that the *next* fragment also opens with a single capital and a stop.
#
#   "No. 4", "Inc." - a known word-abbreviation, which is decisive by itself.
# Two or more initials in a row, closed up ("A.M.") or spaced ("A. M."). Two is the
# evidence that matters: a single trailing initial is usually a real sentence end, as in
# "an A.M. Best rating of A."
_MULTI_INITIAL = re.compile(r"(?:\b[A-Z]\.\s*){2,}$")
_INITIAL_END = re.compile(r"\b[A-Z]\.$")
_INITIAL_START = re.compile(r"^[A-Z]\.")
_WORD_ABBREV = re.compile(
    r"\b(?:No|Nos|Inc|Ltd|Corp|Co|plc|LLC|LLP|Mr|Mrs|Ms|Dr|St|Art|Sec|cf|e\.g|i\.e|etc|vs"
    r"|approx|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.$",
    re.IGNORECASE,
)

# A bare clause heading left dangling at the end of a sentence: "... HEREIN. 5.8 Debarment."
_TRAILING_HEADING = re.compile(r"\s+\d+(?:\.\d+)*\s+[A-Z][A-Za-z]*\.?\s*$")


@dataclass(frozen=True)
class Candidate:
    text: str
    rank: int  # which retrieved chunk it came from; 0 is the best
    position: int  # order within that chunk


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'-]{2,}", text.lower()) if w not in STOPWORDS]


def _redaction_ratio(text: str) -> float:
    """How much of the sentence is redaction marks. CUAD text is full of `[***]`."""
    if not text:
        return 0.0
    return len(re.findall(r"\[\*+\]", text)) * 5 / max(len(text), 1)


def _is_furniture(text: str) -> bool:
    # Note there is deliberately no "mostly uppercase" rule. Limitation-of-liability and
    # warranty-disclaimer clauses are set in capitals precisely so they are conspicuous;
    # they are among the most important provisions in the document, and an earlier version
    # of this filter discarded them as if they were stamps.
    return bool(FURNITURE.search(text)) or _redaction_ratio(text) > 0.35


def sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    if not flat:
        return []
    parts = [s.strip() for s in _SPLIT.split(flat) if s.strip()]
    # Re-join where the split fell after an abbreviation rather than a sentence end.
    merged: list[str] = []
    for part in parts:
        previous = merged[-1] if merged else ""
        joins = bool(previous) and (
            bool(_WORD_ABBREV.search(previous))
            or bool(_MULTI_INITIAL.search(previous))
            or (bool(_INITIAL_END.search(previous)) and bool(_INITIAL_START.match(part)))
        )
        if joins:
            merged[-1] = f"{previous} {part}"
        else:
            merged.append(part)
    # Drop a clause heading that trailed the previous sentence with no body of its own.
    return [_TRAILING_HEADING.sub("", s).strip() or s for s in merged]


def _candidates(
    chunk_texts: Sequence[str], *, per_chunk: int = 14, ceiling: int = 700
) -> list[Candidate]:
    out: list[Candidate] = []
    for rank, chunk in enumerate(chunk_texts):
        for position, sentence in enumerate(sentences(chunk)[:per_chunk]):
            if len(sentence) < 45 or len(sentence) > ceiling:
                continue
            if _is_furniture(sentence):
                continue
            out.append(Candidate(sentence, rank, position))
    return out


def _document_frequency(candidates: Iterable[Candidate]) -> dict[str, int]:
    df: dict[str, int] = {}
    for candidate in candidates:
        for word in set(_tokens(candidate.text)):
            df[word] = df.get(word, 0) + 1
    return df


def summarise(
    query: str,
    chunk_texts: Sequence[str],
    *,
    max_sentences: int = 4,
    max_chars: int = 720,
) -> str:
    """Select the sentences from `chunk_texts` that answer `query`, in reading order."""
    candidates = _candidates(chunk_texts)
    if not candidates:
        # Badly punctuated source: a clause with no sentence breaks in it exceeds the
        # length ceiling and leaves nothing to choose from. Retry without the ceiling and
        # let the trailing trim below cut it to length, rather than return nothing.
        candidates = _candidates(chunk_texts, ceiling=10_000)
    if not candidates:
        return ""

    query_terms = set(_tokens(query))
    df = _document_frequency(candidates)
    total = len(candidates)

    def score(candidate: Candidate) -> float:
        words = _tokens(candidate.text)
        if not words:
            return 0.0
        unique = set(words)
        # Rarity weighting: a term that appears in every candidate separates nothing, so
        # matching it is worth little. This is idf over the candidate pool, not the corpus.
        overlap = sum(math.log(1 + total / (1 + df.get(word, 0))) for word in unique & query_terms)
        base = overlap / math.sqrt(len(unique))
        # Retrieval already ranked the chunks; keep that as a mild prior rather than a
        # hard ordering, so a strong sentence in chunk three can still be chosen.
        base *= 1.0 / (1.0 + 0.28 * candidate.rank)
        # Contract answers are usually the sentence carrying the figure: a cap, a notice
        # period, a percentage, a currency amount.
        if re.search(r"\d", candidate.text):
            base *= 1.16
        # Mild penalty for heavy redaction, which leaves an unreadable sentence.
        base *= 1.0 - min(_redaction_ratio(candidate.text), 0.3)
        return base

    scored = sorted(candidates, key=lambda c: (-score(c), c.rank, c.position))
    if not scored or score(scored[0]) <= 0:
        # Nothing matched the question's vocabulary. Fall back to the best chunk's opening
        # sentences rather than returning an empty answer.
        scored = sorted(candidates, key=lambda c: (c.rank, c.position))

    chosen: list[Candidate] = []
    used: list[set[str]] = []
    length = 0
    for candidate in scored:
        if len(chosen) >= max_sentences or length >= max_chars:
            break
        words = set(_tokens(candidate.text))
        if not words:
            continue
        # Redundancy suppression: a sentence that mostly repeats one already chosen adds
        # nothing, and duplicated boilerplate is exactly how the old version filled up.
        if any(len(words & seen) / max(len(words | seen), 1) > 0.55 for seen in used):
            continue
        chosen.append(candidate)
        used.append(words)
        length += len(candidate.text)

    chosen.sort(key=lambda c: (c.rank, c.position))
    answer = " ".join(c.text for c in chosen).strip()
    if len(answer) > max_chars:
        cut = answer[:max_chars]
        stop = cut.rfind(". ")
        answer = (cut[: stop + 1] if stop > max_chars * 0.5 else cut.rstrip() + "...").strip()
    return answer
