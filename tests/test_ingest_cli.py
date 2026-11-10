import pytest

from govuk_rag.ingestion.cli import main


def test_exits_with_usage_error_when_azure_endpoints_are_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main([])

    assert exit_code == 2
    error = capsys.readouterr().err
    assert "RAG_AZURE_SEARCH_ENDPOINT" in error
    assert "RAG_AZURE_OPENAI_ENDPOINT" in error
    assert "RAG_AZURE_STORAGE_ACCOUNT_URL" in error
