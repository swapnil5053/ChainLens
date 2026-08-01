"""Filesystem anchors.

Every path resolves from the repository root, found by walking up from this file.
Nothing resolves against the current working directory: v1 wrote its vector store and
its uploads wherever the process happened to be launched from.
"""

from __future__ import annotations

from pathlib import Path

_THIS = Path(__file__).resolve()


def _find_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return start.parents[3]


PROJECT_ROOT: Path = _find_root(_THIS)
API_ROOT: Path = PROJECT_ROOT / "apps" / "api"
VAR_DIR: Path = PROJECT_ROOT / "var"
UPLOAD_DIR: Path = VAR_DIR / "uploads"
ARTIFACT_DIR: Path = VAR_DIR / "artifacts"
EVAL_RESULTS_DIR: Path = PROJECT_ROOT / "eval" / "results"
EVAL_DATASET_DIR: Path = PROJECT_ROOT / "eval" / "datasets"


def ensure_runtime_dirs() -> None:
    for directory in (VAR_DIR, UPLOAD_DIR, ARTIFACT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
