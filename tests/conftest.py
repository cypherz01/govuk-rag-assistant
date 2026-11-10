from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from govuk_rag.config import Settings
from govuk_rag.main import create_app


@pytest.fixture
def settings() -> Settings:
    # _env_file=None keeps tests independent of a developer's local .env.
    return Settings(_env_file=None, environment="test")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
