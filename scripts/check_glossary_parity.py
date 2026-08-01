"""Fail if the browser glossary has drifted from the server glossary.

The mock adapter reimplements query expansion so the interface runs with no backend at
all. Duplicated logic diverges silently, and the failure mode here is quiet: the
comparison view would show a smaller gain from expansion than the measured system
delivers, which is a wrong claim rather than a broken screen.

The client copy is allowed to be a subset. Any term it does carry must exist on the server
with the same expansions.

    python scripts/check_glossary_parity.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "apps" / "api" / "chainlens" / "retrieval" / "glossary.yaml"
CLIENT = ROOT / "apps" / "web" / "src" / "api" / "mock" / "glossary.ts"


def load_server() -> dict[str, list[str]]:
    payload = yaml.safe_load(SERVER.read_text(encoding="utf-8"))
    return {str(k).lower(): [str(v) for v in vs] for k, vs in payload["terms"].items()}


def load_client() -> dict[str, list[str]]:
    source = CLIENT.read_text(encoding="utf-8")
    body = re.search(r"GLOSSARY[^=]*=\s*\{(.*?)\n\};", source, re.DOTALL)
    if not body:
        raise SystemExit("could not locate the GLOSSARY object literal in the client file")
    terms: dict[str, list[str]] = {}
    for key, values in re.findall(r'\n\s*"?([A-Za-z0-9 _-]+)"?:\s*\[([^\]]*)\]', body.group(1)):
        terms[key.strip().lower()] = [
            item.strip().strip('"') for item in values.split(",") if item.strip()
        ]
    return terms


def main() -> int:
    server, client = load_server(), load_client()
    problems: list[str] = []
    for term, expansions in sorted(client.items()):
        if term not in server:
            problems.append(f"client term '{term}' does not exist on the server")
            continue
        extra = sorted(set(expansions) - set(server[term]))
        if extra:
            problems.append(f"client term '{term}' expands to {extra}, the server does not")

    for problem in problems:
        print(f"DRIFT  {problem}")
    print(
        json.dumps(
            {
                "server_terms": len(server),
                "client_terms": len(client),
                "server_only_terms": len(set(server) - set(client)),
                "coverage": round(len(client) / len(server), 3),
            },
            indent=2,
        )
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
