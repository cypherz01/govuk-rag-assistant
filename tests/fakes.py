"""In-memory test doubles for the ingestion interfaces."""

from collections.abc import Iterable, Iterator, Sequence

from govuk_rag.ingestion.models import EmbeddedChunk, SourceDocument


class FakeSource:
    def __init__(self, documents: Iterable[SourceDocument]) -> None:
        self.documents = list(documents)

    def list_documents(self) -> Iterator[SourceDocument]:
        return iter(self.documents)


class FakeEmbedder:
    """Returns a deterministic small vector per text and records every call."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0, 0.0] for text in texts]

    @property
    def texts_embedded(self) -> list[str]:
        return [text for call in self.calls for text in call]


class FakeChunkIndex:
    def __init__(self) -> None:
        self.chunks: dict[str, EmbeddedChunk] = {}
        self.ensure_exists_calls = 0

    def ensure_exists(self) -> None:
        self.ensure_exists_calls += 1

    def document_hashes(self) -> dict[str, str]:
        return {c.chunk.document_id: c.chunk.content_hash for c in self.chunks.values()}

    def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None:
        for embedded in chunks:
            self.chunks[embedded.chunk.id] = embedded

    def delete_documents(self, document_ids: Iterable[str]) -> None:
        doomed = set(document_ids)
        self.chunks = {
            chunk_id: embedded
            for chunk_id, embedded in self.chunks.items()
            if embedded.chunk.document_id not in doomed
        }

    def chunk_ids_for(self, document_id: str) -> set[str]:
        return {c.chunk.id for c in self.chunks.values() if c.chunk.document_id == document_id}
