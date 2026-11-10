from dataclasses import dataclass, field
from typing import Any

import pytest

from govuk_rag.answering.chat_model import AzureOpenAIChatModel, ChatMessage


@dataclass
class FakeMessage:
    content: str | None


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeCompletion:
    choices: list[FakeChoice]


@dataclass
class FakeCompletions:
    replies: list[str | None]
    calls: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def create(self, **kwargs: Any) -> FakeCompletion:  # noqa: ANN401 - records any SDK kwargs
        self.calls.append(kwargs)
        return FakeCompletion([FakeChoice(FakeMessage(reply)) for reply in self.replies])


@dataclass
class FakeChat:
    completions: FakeCompletions


@dataclass
class FakeClient:
    chat: FakeChat


def _client(*replies: str | None) -> FakeClient:
    return FakeClient(FakeChat(FakeCompletions(list(replies))))


def test_sends_messages_to_the_deployment_with_an_output_token_cap() -> None:
    client = _client("5.6 weeks [1]")
    model = AzureOpenAIChatModel(client, deployment="chat-deploy", max_output_tokens=300)

    reply = model.complete(
        [
            ChatMessage(role="system", content="Answer from the sources."),
            ChatMessage(role="user", content="How much holiday?"),
        ]
    )

    assert reply == "5.6 weeks [1]"
    [call] = client.chat.completions.calls
    assert call["model"] == "chat-deploy"
    assert call["max_completion_tokens"] == 300
    assert call["temperature"] == 0.0
    assert call["messages"] == [
        {"role": "system", "content": "Answer from the sources."},
        {"role": "user", "content": "How much holiday?"},
    ]


def test_raises_when_the_model_returns_no_content() -> None:
    model = AzureOpenAIChatModel(_client(None), deployment="d", max_output_tokens=10)

    with pytest.raises(RuntimeError, match="no content"):
        model.complete([ChatMessage(role="user", content="hi")])


def test_raises_when_the_model_returns_no_choices() -> None:
    model = AzureOpenAIChatModel(_client(), deployment="d", max_output_tokens=10)

    with pytest.raises(RuntimeError, match="no content"):
        model.complete([ChatMessage(role="user", content="hi")])


def test_rejects_non_positive_token_cap() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        AzureOpenAIChatModel(_client(), deployment="d", max_output_tokens=0)
