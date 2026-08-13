"""Settings must fail fast on missing required values and must never default a secret
(00-decisions.md D-06b / A-06; 01-architecture.md §9 Configuration).
"""

import pytest
from pydantic import ValidationError

from copilot.config import Settings

REQUIRED_ENV = {
    "COPILOT_API_KEY": "test-api-key",
    "COPILOT_DB_PASSWORD": "test-db-password",
}


def test_settings_load_when_required_values_present(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.copilot_api_key == "test-api-key"
    assert settings.copilot_db_password == "test-db-password"


def test_settings_raise_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COPILOT_API_KEY", raising=False)
    monkeypatch.setenv("COPILOT_DB_PASSWORD", "test-db-password")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_raise_when_db_password_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_API_KEY", "test-api-key")
    monkeypatch.delenv("COPILOT_DB_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_no_secret_field_defaults_to_a_concrete_value() -> None:
    """A secret shipping a hardcoded default is how a demo value leaks into production.
    Optional secrets (e.g. anthropic_api_key, unused by the stub provider) may default
    to None -- they may never default to a string.
    """
    for name, field in Settings.model_fields.items():
        if any(marker in name for marker in ("api_key", "password", "secret", "token")):
            assert field.is_required() or field.default is None, (
                f"{name} must be required or default to None, not a concrete value"
            )


def test_defaults_apply_for_optional_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.llm_provider == "anthropic"
    assert settings.llm_max_calls_per_conversation == 8
