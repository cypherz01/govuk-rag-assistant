from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from govuk_rag.answering.answerer import I_DONT_KNOW, Answerer
from govuk_rag.config import Settings
from govuk_rag.main import create_app
from tests.answering_fakes import FakeChatModel, FakeRetriever, retrieved_chunk
from tests.auth import DEMO_KEY_HEADERS


@pytest.fixture
def chat_model() -> FakeChatModel:
    return FakeChatModel("Most workers get 5.6 weeks' paid holiday [1].")


@pytest.fixture
def chat_client(settings: Settings, chat_model: FakeChatModel) -> Iterator[TestClient]:
    retriever = FakeRetriever([retrieved_chunk(relevance=0.8)])
    answerer = Answerer(retriever, chat_model, relevance_threshold=0.4)
    with TestClient(
        create_app(settings, answerer=answerer), headers=DEMO_KEY_HEADERS
    ) as test_client:
        yield test_client


def test_chat_returns_a_cited_answer(chat_client: TestClient) -> None:
    response = chat_client.post("/chat", json={"question": "How much holiday do I get?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Most workers get 5.6 weeks' paid holiday [1].",
        "answered": True,
        "citations": [
            {
                "title": "Holiday entitlement",
                "url": "https://www.gov.uk/holiday-entitlement-rights",
                "snippet": (
                    "Almost all workers are legally entitled to 5.6 weeks' paid holiday a year."
                ),
            }
        ],
    }


def test_chat_returns_i_dont_know_for_off_topic_questions(settings: Settings) -> None:
    model = FakeChatModel("unused")
    answerer = Answerer(
        FakeRetriever([retrieved_chunk(relevance=0.1)]), model, relevance_threshold=0.4
    )

    with TestClient(
        create_app(settings, answerer=answerer), headers=DEMO_KEY_HEADERS
    ) as test_client:
        response = test_client.post("/chat", json={"question": "Who won the 1966 World Cup?"})

    assert response.status_code == 200
    assert response.json() == {"answer": I_DONT_KNOW, "answered": False, "citations": []}
    assert model.calls == []


def test_chat_rejects_a_blank_question(chat_client: TestClient) -> None:
    assert chat_client.post("/chat", json={"question": "  "}).status_code == 422


def test_chat_is_unavailable_when_azure_is_not_configured(client: TestClient) -> None:
    response = client.post("/chat", json={"question": "How much holiday do I get?"})

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_chat_is_described_in_openapi_schema(chat_client: TestClient) -> None:
    schema = chat_client.get("/openapi.json").json()

    assert "/chat" in schema["paths"]
    assert {"ChatRequest", "ChatResponse", "Citation"} <= set(schema["components"]["schemas"])
