import pytest
from pydantic import ValidationError

from govuk_rag.config import Settings


def test_defaults_need_no_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("RAG_ENVIRONMENT", "RAG_LOG_LEVEL", "RAG_AZURE_OPENAI_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "GOV.UK RAG Assistant"
    assert settings.environment == "local"
    assert settings.log_level == "INFO"
    assert settings.azure_openai_endpoint is None
    assert settings.azure_search_endpoint is None


def test_reads_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_ENVIRONMENT", "prod")
    monkeypatch.setenv("RAG_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("RAG_AZURE_SEARCH_ENDPOINT", "https://example.search.windows.net/")

    settings = Settings(_env_file=None)

    assert settings.environment == "prod"
    assert settings.log_level == "WARNING"
    assert str(settings.azure_search_endpoint) == "https://example.search.windows.net/"


def test_rejects_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="staging")  # pyright: ignore[reportArgumentType]


def test_rejects_non_url_endpoint() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, azure_openai_endpoint="not a url")  # pyright: ignore[reportArgumentType]


def test_settings_are_immutable() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValidationError):
        settings.environment = "prod"
