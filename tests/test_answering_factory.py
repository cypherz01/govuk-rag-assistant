import pytest

from govuk_rag.answering.answerer import Answerer
from govuk_rag.answering.factory import build_answerer
from govuk_rag.config import Settings

_ENDPOINTS = {
    "azure_search_endpoint": "https://example.search.windows.net/",
    "azure_openai_endpoint": "https://example.openai.azure.com/",
}


def test_builds_an_answerer_when_search_and_openai_are_configured() -> None:
    answerer = build_answerer(Settings.model_validate(_ENDPOINTS))

    assert isinstance(answerer, Answerer)


@pytest.mark.parametrize("missing", list(_ENDPOINTS))
def test_returns_none_when_an_endpoint_is_missing(missing: str) -> None:
    endpoints = {name: url for name, url in _ENDPOINTS.items() if name != missing}

    assert build_answerer(Settings.model_validate(endpoints)) is None
