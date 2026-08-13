<#
.SYNOPSIS
    Windows equivalent of the Makefile targets (`make` is not available by default on
    Windows). Usage: .\scripts\dev.ps1 <target>

    Targets are kept 1:1 with the Makefile: sync, fmt, fmt-check, lint, typecheck,
    import-lint, test, test-cov, audit, ci, up, down, logs, ingest, smoke, diagram,
    newman, clean
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "sync", "fmt", "fmt-check", "lint", "typecheck", "import-lint",
        "test", "test-cov", "audit", "ci", "up", "down", "logs",
        "ingest", "smoke", "diagram", "newman", "clean"
    )]
    [string]$Target
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([string]$Command)
    Write-Host "> $Command" -ForegroundColor Cyan
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Command" }
}

switch ($Target) {
    "sync"        { Invoke-Checked "uv sync --all-groups" }
    "fmt"         { Invoke-Checked "uv run ruff format ." }
    "fmt-check"   { Invoke-Checked "uv run ruff format --check ." }
    "lint"        { Invoke-Checked "uv run ruff check ." }
    "typecheck"   {
        Invoke-Checked "uv run mypy --strict apps/backend/src/copilot/domain apps/backend/src/copilot/compliance apps/backend/src/copilot/mcp apps/backend/src/copilot/llm"
    }
    "import-lint" { Invoke-Checked "uv run lint-imports" }
    "test"        { Invoke-Checked "uv run pytest --cov --cov-report=term-missing --cov-report=xml" }
    "test-cov"    { Invoke-Checked "uv run pytest --cov --cov-report=term-missing --cov-report=xml --cov-fail-under=85" }
    "audit"       { Invoke-Checked "uv run pip-audit" }
    "ci"          {
        Invoke-Checked "uv run ruff format --check ."
        Invoke-Checked "uv run ruff check ."
        Invoke-Checked "uv run mypy --strict apps/backend/src/copilot/domain apps/backend/src/copilot/compliance apps/backend/src/copilot/mcp apps/backend/src/copilot/llm"
        Invoke-Checked "uv run lint-imports"
        Invoke-Checked "uv run pytest --cov --cov-report=term-missing --cov-report=xml"
        Invoke-Checked "uv run pip-audit"
    }
    "up"          { Invoke-Checked "docker compose up --build" }
    "down"        { Invoke-Checked "docker compose down -v" }
    "logs"        { Invoke-Checked "docker compose logs -f" }
    "ingest"      { Invoke-Checked "docker compose --profile batch run --rm rag-ingest" }
    "smoke"       { Invoke-Checked "uv run python scripts/smoke.py" }
    "diagram"     { Invoke-Checked "uv run python scripts/render_diagrams.py" }
    "newman"      {
        Invoke-Checked "npx --yes newman run postman/Alarm-API-Simulator.postman_collection.json --env-var baseUrl=http://localhost:8000"
        Invoke-Checked "npx --yes newman run postman/chaining/Alarm-API-Chaining.postman_collection.json --env-var baseUrl=http://localhost:8000"
        Invoke-Checked "npx --yes newman run postman/scenarios/Alarm-API-Scenarios.postman_collection.json --env-var baseUrl=http://localhost:8000"
    }
    "clean"       {
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .pytest_cache, .mypy_cache, .ruff_cache, htmlcov, coverage.xml, .coverage
    }
}
