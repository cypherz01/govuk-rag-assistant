"""Finding the indexed chunks most likely to answer a question."""

import math
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Protocol

from azure.search.documents.models import VectorizedQuery, VectorQuery
from pydantic import BaseModel, ConfigDict, HttpUrl

from govuk_rag.ingestion.embeddings import Embedder

_VECTOR_FIELD = "content_vector"


class RetrievedChunk(BaseModel):
    """A chunk returned for a question, with how relevant it is to that question."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    url: HttpUrl
    content: str
    relevance: float


class Retriever(Protocol):
    def retrieve(self, question: str) -> list[RetrievedChunk]:
        """Return the best-matching chunks, best first."""
        ...


class HybridSearchClient(Protocol):
    """The slice of ``azure.search.documents.SearchClient`` used for retrieval."""

    def search(
        self,
        search_text: str,
        *,
        vector_queries: list[VectorQuery],
        select: list[str],
        top: int,
    ) -> Iterator[Mapping[str, Any]]: ...


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine of the angle between two vectors; 0.0 if either is all zeros."""
    if len(a) != len(b):
        msg = f"vectors differ in length: {len(a)} and {len(b)}"
        raise ValueError(msg)
    norms = math.hypot(*a) * math.hypot(*b)
    if norms == 0.0:
        return 0.0
    return math.sumprod(a, b) / norms


class AzureSearchRetriever:
    """Hybrid (keyword + vector) retrieval from Azure AI Search.

    Hybrid search ranks well, but its fused score (Reciprocal Rank Fusion) only reflects rank:
    the top hit scores about the same whether or not it is relevant. So relevance is measured
    separately, as the cosine similarity between the question and each chunk's stored vector,
    which gives a threshold something meaningful to compare against.
    """

    def __init__(self, client: HybridSearchClient, embedder: Embedder, *, top: int = 5) -> None:
        if top < 1:
            msg = "top must be at least 1"
            raise ValueError(msg)
        self._client = client
        self._embedder = embedder
        self._top = top

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        [question_vector] = self._embedder.embed([question])
        results = self._client.search(
            question,
            vector_queries=[
                VectorizedQuery(
                    vector=question_vector,
                    k_nearest_neighbors=self._top,
                    fields=_VECTOR_FIELD,
                )
            ],
            select=["title", "url", "content", _VECTOR_FIELD],
            top=self._top,
        )
        return [
            RetrievedChunk(
                title=str(row["title"]),
                url=HttpUrl(str(row["url"])),
                content=str(row["content"]),
                relevance=cosine_similarity(question_vector, _as_vector(row[_VECTOR_FIELD])),
            )
            for row in results
        ]


def _as_vector(value: object) -> list[float]:
    if not isinstance(value, list):
        msg = f"expected a vector, got {type(value).__name__}"
        raise TypeError(msg)
    return [float(x) for x in value]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
