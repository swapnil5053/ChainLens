# Convenience targets. The compose path is the documented production path; the local
# targets exist because the environment this was rebuilt in had no Docker.

.PHONY: up down demo migrate index eval report gate test lint types check localpg

up:
	docker compose -f infra/docker-compose.yml up --build

down:
	docker compose -f infra/docker-compose.yml down -v

demo: up

# Local, Docker-free path. Starts PostgreSQL 16 with pgvector in-process.
localpg:
	CHAINLENS_LOCAL_PG=1 python scripts/local_postgres.py

migrate:
	CHAINLENS_LOCAL_PG=1 python scripts/migrate.py

index:
	CHAINLENS_LOCAL_PG=1 python -m eval.build_index

eval:
	CHAINLENS_LOCAL_PG=1 python -m eval.run

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

check: lint test
	python scripts/check_no_emoji.py
