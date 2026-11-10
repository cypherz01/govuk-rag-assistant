from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from govuk_rag.answering.answerer import Answerer
from govuk_rag.config import Settings
from govuk_rag.main import create_app
from tests.answering_fakes import FakeChatModel, FakeRetriever, retrieved_chunk
from tests.auth import DEMO_KEY

QUESTION = {"question": "How much holiday do I get?"}


def _answerer(model: FakeChatModel) -> Answerer:
    return Answerer(FakeRetriever([retrieved_chunk()]), model, relevance_threshold=0.4)


@pytest.fixture
def model() -> FakeChatModel:
    return FakeChatModel("5.6 weeks [1].")


@pytest.fixture
def anonymous_client(settings: Settings, model: FakeChatModel) -> Iterator[TestClient]:
    """A client that sends no demo key unless a test adds one."""
    with TestClient(create_app(settings, answerer=_answerer(model))) as test_client:
        yield test_client


def test_chat_accepts_the_demo_key(anonymous_client: TestClient) -> None:
    response = anonymous_client.post("/chat", json=QUESTION, headers={"X-Demo-Key": DEMO_KEY})

    assert response.status_code == 200
    assert response.json()["answered"] is True


def test_chat_rejects_a_request_without_a_key(
    anonymous_client: TestClient, model: FakeChatModel
) -> None:
    response = anonymous_client.post("/chat", json=QUESTION)

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid demo key."
    assert model.calls == []


@pytest.mark.parametrize("key", ["wrong-key", "", DEMO_KEY.upper(), f"{DEMO_KEY} "])
def test_chat_rejects_a_wrong_key(
    anonymous_client: TestClient, model: FakeChatModel, key: str
) -> None:
    response = anonymous_client.post("/chat", json=QUESTION, headers={"X-Demo-Key": key})

    assert response.status_code == 401
    assert model.calls == []


def test_key_is_checked_before_the_request_body(anonymous_client: TestClient) -> None:
    """Callers without a key learn nothing, not even validation errors."""
    response = anonymous_client.post("/chat", json={"question": ""})

    assert response.status_code == 401


def test_chat_is_closed_when_no_demo_key_is_configured() -> None:
    model = FakeChatModel("unused")
    app = create_app(Settings(environment="test"), answerer=_answerer(model))

    with TestClient(app) as test_client:
        response = test_client.post("/chat", json=QUESTION, headers={"X-Demo-Key": "anything"})

    assert response.status_code == 503
    assert "demo key" in response.json()["detail"].lower()
    assert model.calls == []


def test_health_does_not_need_a_key(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/health").status_code == 200


def test_demo_key_is_documented_as_a_security_scheme(anonymous_client: TestClient) -> None:
    schema = anonymous_client.get("/openapi.json").json()

    [scheme] = schema["components"]["securitySchemes"].values()
    assert scheme == {"type": "apiKey", "in": "header", "name": "X-Demo-Key"}
    assert schema["paths"]["/chat"]["post"]["security"]


def test_demo_key_is_read_from_the_environment_and_never_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_DEMO_KEY", "from-the-env")

    settings = Settings()

    assert settings.demo_key == SecretStr("from-the-env")
    assert "from-the-env" not in repr(settings)
