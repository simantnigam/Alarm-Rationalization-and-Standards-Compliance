.PHONY: sync fmt fmt-check lint typecheck import-lint test test-cov audit ci \
        up down logs ingest smoke diagram newman clean

# Windows has no `make` by default — use `.\scripts\dev.ps1 <target>` instead.
# Targets below are kept 1:1 with scripts/dev.ps1 so either can be used interchangeably.

sync:
	uv sync --all-groups

fmt:
	uv run ruff format .

fmt-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run mypy --strict \
		apps/backend/src/copilot/domain \
		apps/backend/src/copilot/compliance \
		apps/backend/src/copilot/mcp \
		apps/backend/src/copilot/llm

import-lint:
	uv run lint-imports

test:
	uv run pytest --cov --cov-report=term-missing --cov-report=xml

test-cov:
	uv run pytest --cov --cov-report=term-missing --cov-report=xml --cov-fail-under=85

audit:
	uv run pip-audit

ci: fmt-check lint typecheck import-lint test audit

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

ingest:
	docker compose --profile batch run --rm rag-ingest

smoke:
	uv run python scripts/smoke.py

diagram:
	uv run python scripts/render_diagrams.py

newman:
	npx --yes newman run postman/Alarm-API-Simulator.postman_collection.json --env-var baseUrl=http://localhost:8000
	npx --yes newman run postman/chaining/Alarm-API-Chaining.postman_collection.json --env-var baseUrl=http://localhost:8000
	npx --yes newman run postman/scenarios/Alarm-API-Scenarios.postman_collection.json --env-var baseUrl=http://localhost:8000

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml .coverage
