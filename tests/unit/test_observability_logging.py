"""configure_logging must actually produce working, redacted, JSON log output --
not just declare a processor chain that's never exercised.
"""

import json

import pytest
import structlog

from copilot.observability.logging import configure_logging


@pytest.fixture(autouse=True)
def _reset_structlog() -> None:
    yield
    structlog.reset_defaults()


def test_configure_logging_produces_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO")
    logger = structlog.get_logger()
    logger.info("alarm_summary_requested", asset_id="NP-U1-BFP-101")

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["event"] == "alarm_summary_requested"
    assert payload["asset_id"] == "NP-U1-BFP-101"


def test_configure_logging_redacts_secrets_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO")
    logger = structlog.get_logger()
    logger.info("mcp_call", Authorization="Bearer super-secret-value")

    captured = capsys.readouterr()
    assert "super-secret-value" not in captured.out
