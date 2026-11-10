from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest
from azure.search.documents.models import VectorizedQuery, VectorQuery

from govuk_rag.answering.retrieval import AzureSearchRetriever, cosine_similarity


class FixedEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self.vector for _ in texts]


class FakeHybridSearchClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def search(
        self,
        search_text: str,
        *,
        vector_queries: list[VectorQuery],
        select: list[str],
        top: int,
    ) -> Iterator[Mapping[str, Any]]:
        self.calls.append(
            {
                "search_text": search_text,
                "vector_queries": vector_queries,
                "select": select,
                "top": top,
            }
        )
        return iter(self.rows)


def _row(title: str, slug: str, vector: list[float]) -> dict[str, Any]:
    return {
        "title": title,
        "url": f"https://www.gov.uk/{slug}",
        "content": f"{title} content",
        "content_vector": vector,
        "@search.score": 0.03,
    }


def test_runs_one_hybrid_query_with_the_question_text_and_its_embedding() -> None:
    embedder = FixedEmbedder([1.0, 0.0])
    client = FakeHybridSearchClient([])

    AzureSearchRetriever(client, embedder, top=4).retrieve("How much holiday do I get?")

    assert embedder.calls == [["How much holiday do I get?"]]
    [call] = client.calls
    assert call["search_text"] == "How much holiday do I get?"
    assert call["top"] == 4
    [vector_query] = call["vector_queries"]
    assert isinstance(vector_query, VectorizedQuery)
    assert vector_query.vector == [1.0, 0.0]
    assert vector_query.fields == "content_vector"
    assert vector_query.k_nearest_neighbors == 4
    assert set(call["select"]) >= {"title", "url", "content", "content_vector"}


def test_scores_each_chunk_by_cosine_similarity_to_the_question() -> None:
    client = FakeHybridSearchClient(
        [
            _row("Holiday entitlement", "holiday-entitlement-rights", [1.0, 0.0]),
            _row("Statutory Sick Pay", "statutory-sick-pay", [0.0, 2.0]),
        ]
    )

    chunks = AzureSearchRetriever(client, FixedEmbedder([3.0, 0.0])).retrieve("holiday")

    assert [(c.title, c.relevance) for c in chunks] == [
        ("Holiday entitlement", pytest.approx(1.0)),
        ("Statutory Sick Pay", pytest.approx(0.0)),
    ]
    assert str(chunks[0].url) == "https://www.gov.uk/holiday-entitlement-rights"
    assert chunks[0].content == "Holiday entitlement content"


def test_keeps_the_search_ranking_order() -> None:
    client = FakeHybridSearchClient(
        [
            _row("Ranked first", "a", [0.0, 1.0]),
            _row("Ranked second", "b", [1.0, 0.0]),
        ]
    )

    chunks = AzureSearchRetriever(client, FixedEmbedder([1.0, 0.0])).retrieve("q")

    assert [c.title for c in chunks] == ["Ranked first", "Ranked second"]


def test_rejects_non_positive_top() -> None:
    with pytest.raises(ValueError, match="top"):
        AzureSearchRetriever(FakeHybridSearchClient([]), FixedEmbedder([1.0]), top=0)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ([1.0, 0.0], [1.0, 0.0], 1.0),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 0.0], [-1.0, 0.0], -1.0),
        ([1.0, 1.0], [2.0, 2.0], 1.0),
        ([0.0, 0.0], [1.0, 0.0], 0.0),
    ],
)
def test_cosine_similarity(a: list[float], b: list[float], expected: float) -> None:
    assert cosine_similarity(a, b) == pytest.approx(expected)


def test_cosine_similarity_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="length"):
        cosine_similarity([1.0], [1.0, 0.0])
