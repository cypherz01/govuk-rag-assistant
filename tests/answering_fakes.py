"""In-memory test doubles for the answering interfaces."""

from collections.abc import Iterable, Sequence

from pydantic import HttpUrl

from govuk_rag.answering.chat_model import ChatMessage
from govuk_rag.answering.retrieval import RetrievedChunk


class FakeRetriever:
    """Returns fixed chunks and records every question it was asked."""

    def __init__(self, chunks: Iterable[RetrievedChunk] = ()) -> None:
        self.chunks = list(chunks)
        self.questions: list[str] = []

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        self.questions.append(question)
        return list(self.chunks)


class FakeChatModel:
    """Returns a fixed reply and records the messages of every call."""

    def __init__(self, reply: str = "") -> None:
        self.reply = reply
        self.calls: list[list[ChatMessage]] = []

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(list(messages))
        return self.reply


def retrieved_chunk(
    title: str = "Holiday entitlement",
    *,
    slug: str = "holiday-entitlement-rights",
    content: str = "Almost all workers are legally entitled to 5.6 weeks' paid holiday a year.",
    relevance: float = 0.8,
) -> RetrievedChunk:
    return RetrievedChunk(
        title=title,
        url=HttpUrl(f"https://www.gov.uk/{slug}"),
        content=content,
        relevance=relevance,
    )
