"""Answering a question: retrieve, gate on relevance, ask the model, attach citations."""

import re

from govuk_rag.answering.chat_model import ChatModel
from govuk_rag.answering.prompt import NO_ANSWER, build_messages
from govuk_rag.answering.retrieval import RetrievedChunk, Retriever
from govuk_rag.models import ChatResponse, Citation

I_DONT_KNOW = (
    "I don't know. The guidance I have doesn't cover that question, "
    "so please check with HR or GOV.UK directly."
)

_MARKER = re.compile(r"\[(\d+)\]")
_ELLIPSIS = "…"


class Answerer:
    def __init__(
        self,
        retriever: Retriever,
        chat_model: ChatModel,
        *,
        relevance_threshold: float,
        snippet_chars: int = 300,
    ) -> None:
        self._retriever = retriever
        self._chat_model = chat_model
        self._relevance_threshold = relevance_threshold
        self._snippet_chars = snippet_chars

    def answer(self, question: str) -> ChatResponse:
        relevant = [
            chunk
            for chunk in self._retriever.retrieve(question)
            if chunk.relevance >= self._relevance_threshold
        ]
        if not relevant:
            # Nothing close enough: skip the model entirely and save the tokens.
            return _i_dont_know()

        reply = self._chat_model.complete(build_messages(question, relevant)).strip()
        # The model is told to reply with only the sentinel, but sometimes explains first.
        if NO_ANSWER in reply:
            return _i_dont_know()

        answer, used = _renumber_citations(reply, len(relevant))
        cited = [relevant[i] for i in used] if used else relevant
        return ChatResponse(
            answer=answer,
            answered=True,
            citations=[self._citation(chunk) for chunk in cited],
        )

    def _citation(self, chunk: RetrievedChunk) -> Citation:
        return Citation(
            title=chunk.title, url=chunk.url, snippet=_snippet(chunk.content, self._snippet_chars)
        )


def _i_dont_know() -> ChatResponse:
    return ChatResponse(answer=I_DONT_KNOW, answered=False)


def _renumber_citations(reply: str, source_count: int) -> tuple[str, list[int]]:
    """Renumber ``[n]`` markers 1, 2, ... in order of first use, dropping any that match no source.

    Returns the rewritten reply and the 0-based indexes of the sources used, in citation order.
    """
    used: list[int] = []

    def renumber(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if not 0 <= index < source_count:
            return ""
        if index not in used:
            used.append(index)
        return f"[{used.index(index) + 1}]"

    return _MARKER.sub(renumber, reply), used


def _snippet(text: str, max_chars: int) -> str:
    """The start of ``text``, cut at a word boundary if it is longer than ``max_chars``."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    mid_word = not text[max_chars].isspace() and not cut[-1].isspace()
    if mid_word and len(cut.split()) > 1:
        cut = cut.rsplit(maxsplit=1)[0]  # drop the partial last word
    return cut.rstrip() + _ELLIPSIS
