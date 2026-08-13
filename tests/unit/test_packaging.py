"""Phase 0 exit-gate smoke test: every workspace package must be importable from one
environment. The .importlinter contracts are checked separately by `lint-imports`.
"""

import importlib


def test_all_packages_import_cleanly() -> None:
    packages = [
        "copilot",
        "copilot.api",
        "copilot.graph",
        "copilot.planning",
        "copilot.mcp",
        "copilot.llm",
        "copilot.llm.adapters",
        "copilot.rag",
        "copilot.compliance",
        "copilot.domain",
        "copilot.observability",
        "frontend",
        "connectors",
        "connectors.alarm_api",
        "mcp_servers",
        "mcp_servers.alarm_management",
        "alarm_api_simulator",
        "rag",
        "rag.ingestion",
        "rag.retrieval",
    ]
    for name in packages:
        importlib.import_module(name)
