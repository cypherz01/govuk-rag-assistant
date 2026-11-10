import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from govuk_rag.config import Settings
from govuk_rag.main import create_app


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent of a developer's local .env file and RAG_* variables."""
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith("RAG_"):
            monkeypatch.delenv(name)


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
