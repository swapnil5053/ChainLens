"""Query preprocessing.

Contracts use the long form of a term; analysts type the abbreviation. Expansion adds
alternative surface forms so the lexical arm has something to match. Whether it helps is
measured, not assumed: see the ``+expansion`` rows in ``docs/RETRIEVAL.md``.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

GLOSSARY_PATH = Path(__file__).with_name("glossary.yaml")


@lru_cache(maxsize=4)
def load_glossary(path: Path = GLOSSARY_PATH) -> dict[str, tuple[str, ...]]:
    payload: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        str(key).lower(): tuple(str(value) for value in values)
        for key, values in payload.get("terms", {}).items()
    }


def expand_query(query: str, glossary: dict[str, tuple[str, ...]] | None = None) -> str:
    glossary = glossary if glossary is not None else load_glossary()
    lowered = query.lower()
    additions: list[str] = []
    for term, alternatives in glossary.items():
        hit = (
            term in lowered
            if " " in term
            else re.search(rf"\b{re.escape(term)}\b", lowered) is not None
        )
        if not hit:
            continue
        for alternative in alternatives:
            if alternative.lower() not in lowered and alternative not in additions:
                additions.append(alternative)
    return f"{query} {' '.join(additions)}" if additions else query
