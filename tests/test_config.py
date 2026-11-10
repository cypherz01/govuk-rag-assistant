import pytest
from pydantic import ValidationError

from govuk_rag.config import Settings


def test_defaults_need_no_environment_variables() -> None:
    settings = Settings()

    assert settings.app_name == "GOV.UK RAG Assistant"
    assert settings.environment == "local"
    assert settings.log_level == "INFO"
    assert settings.azure_openai_endpoint is None
    assert settings.azure_search_endpoint is None


def test_reads_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_ENVIRONMENT", "prod")
    monkeypatch.setenv("RAG_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("RAG_AZURE_SEARCH_ENDPOINT", "https://example.search.windows.net/")

    settings = Settings()

    assert settings.environment == "prod"
    assert settings.log_level == "WARNING"
    assert str(settings.azure_search_endpoint) == "https://example.search.windows.net/"


def test_rejects_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="staging")  # pyright: ignore[reportArgumentType]


def test_rejects_non_url_endpoint() -> None:
    with pytest.raises(ValidationError):
        Settings(azure_openai_endpoint="not a url")  # pyright: ignore[reportArgumentType]


def test_settings_are_immutable() -> None:
    settings = Settings()

    with pytest.raises(ValidationError):
        settings.environment = "prod"


def test_ingestion_defaults() -> None:
    settings = Settings()

    assert settings.azure_storage_account_url is None
    assert settings.blob_container_name == "govuk-guidance"
    assert settings.search_index_name == "govuk-guidance"
    assert settings.embedding_deployment == "text-embedding-3-small"
    assert settings.embedding_dimensions == 1536
    assert settings.chunk_max_chars == 1500
    assert settings.chunk_overlap_chars == 200


def test_rejects_overlap_not_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError, match="chunk_overlap_chars"):
        Settings(chunk_max_chars=500, chunk_overlap_chars=500)


@pytest.mark.parametrize("field", ["embedding_dimensions", "chunk_max_chars"])
def test_rejects_non_positive_sizes(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({field: 0})
