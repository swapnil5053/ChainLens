"""Apply Alembic migrations, starting the local server first when configured.

    CHAINLENS_LOCAL_PG=1 python scripts/migrate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.bootstrap import ensure_database  # noqa: E402


def main() -> int:
    dsn = ensure_database()
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps" / "api" / "alembic"))
    config.set_main_option("sqlalchemy.url", dsn)
    command.upgrade(config, "head")
    print(f"migrated: {dsn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
