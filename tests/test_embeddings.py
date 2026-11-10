from dataclasses import dataclass, field

import pytest

from govuk_rag.ingestion.embeddings import AzureOpenAIEmbedder


@dataclass
class FakeEmbeddingItem:
    index: int
    embedding: list[float]


@dataclass
class FakeEmbeddingResponse:
    data: list[FakeEmbeddingItem]


@dataclass
class FakeEmbeddingsResource:
    calls: list[tuple[list[str], str]] = field(default_factory=list[tuple[list[str], str]])
    drop_one: bool = False

    def create(self, *, input: list[str], model: str) -> FakeEmbeddingResponse:  # noqa: A002
        self.calls.append((input, model))
        # Return items out of order to prove the embedder sorts by index.
        items = [FakeEmbeddingItem(i, [float(len(text))]) for i, text in enumerate(input)]
        if self.drop_one:
            items = items[1:]
        return FakeEmbeddingResponse(list(reversed(items)))


@dataclass
class FakeClient:
    embeddings: FakeEmbeddingsResource = field(default_factory=FakeEmbeddingsResource)


def test_batches_requests_and_preserves_input_order() -> None:
    client = FakeClient()
    embedder = AzureOpenAIEmbedder(client, deployment="embed-deploy", batch_size=2)

    vectors = embedder.embed(["a", "bb", "ccc", "dddd", "eeeee"])

    assert vectors == [[1.0], [2.0], [3.0], [4.0], [5.0]]
    assert [len(batch) for batch, _ in client.embeddings.calls] == [2, 2, 1]
    assert {model for _, model in client.embeddings.calls} == {"embed-deploy"}


def test_empty_input_makes_no_requests() -> None:
    client = FakeClient()

    assert AzureOpenAIEmbedder(client, deployment="d").embed([]) == []
    assert client.embeddings.calls == []


def test_raises_when_response_is_missing_vectors() -> None:
    client = FakeClient(FakeEmbeddingsResource(drop_one=True))

    with pytest.raises(RuntimeError, match="expected 2 embeddings, got 1"):
        AzureOpenAIEmbedder(client, deployment="d").embed(["a", "b"])
