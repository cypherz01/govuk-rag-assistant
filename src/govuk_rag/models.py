"""Request and response models for the HTTP API."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

MAX_HISTORY_TURNS = 4
MAX_QUESTION_LENGTH = 1000

Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH)
]


class ApiModel(BaseModel):
    """Base for API models: immutable and strict about unexpected fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    version: str
    environment: str


class ChatTurn(ApiModel):
    """One earlier message in the conversation, sent back by the browser."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(ApiModel):
    question: Question
    history: list[ChatTurn] = Field(default_factory=list[ChatTurn], max_length=MAX_HISTORY_TURNS)


class Citation(ApiModel):
    """A source chunk used to answer, linking back to its GOV.UK page."""

    title: str
    url: HttpUrl
    snippet: str


class ChatResponse(ApiModel):
    answer: str
    answered: bool = Field(
        description="False when the documents don't cover the question ('I don't know').",
    )
    citations: list[Citation] = Field(default_factory=list[Citation])
