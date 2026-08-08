"""Content addressing.

v1 re-embedded a document end to end every time the same file was uploaded again. The
hash is taken over the raw bytes, so an identical upload is recognised before parsing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_BLOCK = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_BLOCK):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
