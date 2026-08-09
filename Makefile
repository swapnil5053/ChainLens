# Convenience targets.
#
# `demo` brings up the full compose stack. `demo-local` needs no Docker at all and runs
# an embedded PostgreSQL instead. The normal path is neither: see RUNNING.md.

.PHONY: up down demo demo-local migrate index eval eval-extraction report gate seed test lint types check web web-verify

up:
	docker compose -f infra/docker-compose.yml up --build -d
	@echo "waiting for the API to report healthy"
	@until curl -fsS http://localhost:8000/health >/dev/null 2>&1; do sleep 2; done
	@echo "API healthy"

down:
	docker compose -f infra/docker-compose.yml down -v

# Bring everything up and put three real contracts in it, so the first screen is not empty.
demo: up
	docker compose -f infra/docker-compose.yml exec -T api python scripts/seed.py
	@echo "open http://localhost:3000"

# The Docker-free equivalent, verified.
# One command: start the embedded Postgres, migrate, index if needed, and serve.
serve:
	CHAINLENS_LOCAL_PG=1 python scripts/serve.py

demo-local: migrate seed
	@echo "starting the API on http://localhost:8000"
	CHAINLENS_LOCAL_PG=1 python -m uvicorn chainlens.main:app --app-dir apps/api --port 8000

migrate:
	CHAINLENS_LOCAL_PG=1 python scripts/migrate.py

seed:
	CHAINLENS_LOCAL_PG=1 python scripts/seed.py

index:
	CHAINLENS_LOCAL_PG=1 python -m eval.build_index

eval:
	CHAINLENS_LOCAL_PG=1 python -m eval.run

eval-extraction:
	python -m eval.run_extraction

report:
	python -m eval.report

gate:
	python -m eval.gate

test:
	python -m pytest apps/api/tests -q

lint:
	python -m ruff check . && python -m ruff format --check .

types:
	python -m mypy

check: lint types test
	python scripts/check_no_emoji.py
	python scripts/contrast.py
	python scripts/check_glossary_parity.py

web:
	cd apps/web && npm run dev

web-verify:
	cd apps/web && npm run verify
