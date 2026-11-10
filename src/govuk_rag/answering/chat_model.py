"""Generating replies with a chat model."""

from collections.abc import Sequence
from typing import Literal, Protocol

from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class ChatModel(Protocol):
    def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return the model's reply to the conversation."""
        ...


class _Message(Protocol):
    @property
    def content(self) -> str | None: ...


class _Choice(Protocol):
    @property
    def message(self) -> _Message: ...


class _Completion(Protocol):
    @property
    def choices(self) -> Sequence[_Choice]: ...


class _CompletionsResource(Protocol):
    def create(
        self,
        *,
        model: str,
        messages: list[ChatCompletionMessageParam],
        max_completion_tokens: int,
        temperature: float,
    ) -> _Completion: ...


class _ChatResource(Protocol):
    @property
    def completions(self) -> _CompletionsResource: ...


class ChatCompletionsClient(Protocol):
    """The slice of the OpenAI SDK client used here (satisfied by ``openai.AzureOpenAI``)."""

    @property
    def chat(self) -> _ChatResource: ...


class AzureOpenAIChatModel:
    """Chat completions from an Azure OpenAI deployment, deterministic and length-capped."""

    def __init__(
        self,
        client: ChatCompletionsClient,
        *,
        deployment: str,
        max_output_tokens: int,
        temperature: float = 0.0,
    ) -> None:
        if max_output_tokens < 1:
            msg = "max_output_tokens must be at least 1"
            raise ValueError(msg)
        self._client = client
        self._deployment = deployment
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        completion = self._client.chat.completions.create(
            model=self._deployment,
            messages=[_to_param(m) for m in messages],
            max_completion_tokens=self._max_output_tokens,
            temperature=self._temperature,
        )
        content = completion.choices[0].message.content if completion.choices else None
        if content is None:
            msg = "chat model returned no content"
            raise RuntimeError(msg)
        return content


def _to_param(message: ChatMessage) -> ChatCompletionMessageParam:
    match message.role:
        case "system":
            return ChatCompletionSystemMessageParam(role="system", content=message.content)
        case "user":
            return ChatCompletionUserMessageParam(role="user", content=message.content)
        case "assistant":
            return ChatCompletionAssistantMessageParam(role="assistant", content=message.content)
