"""Fail if an emoji appears anywhere in the repository.

v1 had emoji in the interface, in log lines and in status strings. Rather than remove
them once and hope, this runs as a pre-commit hook and in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

RANGES = (
    (0x1F300, 0x1FAFF),
    (0x1F000, 0x1F2FF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0xFE0F, 0xFE0F),
)
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2", ".pkl"}
SKIP_PARTS = {
    ".git",
    "node_modules",
    "var",
    ".next",
    "dist",
    "corpus",
    "fixtures",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}


def iter_files(root: Path) -> list[Path]:
    """Walk the tree, pruning skip directories instead of filtering after the fact.

    rglob descends into node_modules before discarding it, which turns a pre-commit hook
    into a several-second pause. Pruning during the walk keeps it instant.
    """
    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name in SKIP_PARTS:
                continue
            if entry.is_dir():
                stack.append(entry)
            elif entry.is_file():
                found.append(entry)
    return found


def is_emoji(char: str) -> bool:
    point = ord(char)
    return any(low <= point <= high for low, high in RANGES)


def check(path: Path) -> list[str]:
    if path.suffix.lower() in SKIP_SUFFIXES or set(path.parts) & SKIP_PARTS:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for char in line:
            if is_emoji(char):
                problems.append(f"{path}:{number}: emoji U+{ord(char):04X}")
                break
    return problems


def main(argv: list[str]) -> int:
    targets = [Path(arg) for arg in argv[1:]] or iter_files(Path())
    problems = [problem for target in targets if target.is_file() for problem in check(target)]
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
