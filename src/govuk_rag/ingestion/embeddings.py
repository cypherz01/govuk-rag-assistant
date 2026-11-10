"""Turning text into embedding vectors."""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...


class _EmbeddingItem(Protocol):
    @property
    def index(self) -> int: ...

    @property
    def embedding(self) -> list[float]: ...


class _EmbeddingResponse(Protocol):
    @property
    def data(self) -> Sequence[_EmbeddingItem]: ...


class _EmbeddingsResource(Protocol):
    def create(self, *, input: list[str], model: str) -> _EmbeddingResponse: ...  # noqa: A002


class EmbeddingsClient(Protocol):
    """The slice of the OpenAI SDK client used here (satisfied by ``openai.AzureOpenAI``)."""

    @property
    def embeddings(self) -> _EmbeddingsResource: ...


class AzureOpenAIEmbedder:
    """Embeds text with an Azure OpenAI deployment, in batches."""

    def __init__(self, client: EmbeddingsClient, *, deployment: str, batch_size: int = 64) -> None:
        if batch_size < 1:
            msg = "batch_size must be at least 1"
            raise ValueError(msg)
        self._client = client
        self._deployment = deployment
        self._batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = self._client.embeddings.create(input=batch, model=self._deployment)
            if len(response.data) != len(batch):
                msg = f"expected {len(batch)} embeddings, got {len(response.data)}"
                raise RuntimeError(msg)
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda i: i.index))
        return vectors
