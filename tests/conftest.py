import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from govuk_rag.config import Settings
from govuk_rag.main import create_app
from tests.auth import DEMO_KEY, DEMO_KEY_HEADERS


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent of a developer's local .env file and RAG_* variables."""
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith("RAG_"):
            monkeypatch.delenv(name)


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", demo_key=SecretStr(DEMO_KEY))


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A client for the app with no Azure configured, sending the demo key."""
    with TestClient(create_app(settings), headers=DEMO_KEY_HEADERS) as test_client:
        yield test_client
