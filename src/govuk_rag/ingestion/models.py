"""Data passed between the ingestion stages."""

import hashlib
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceDocument(_Frozen):
    """One page of guidance as read from a source connector."""

    id: str = Field(min_length=1)
    title: str
    url: HttpUrl
    text: str

    @cached_property
    def content_hash(self) -> str:
        """Fingerprint of everything that ends up in the index, used to skip unchanged pages."""
        payload = "\x1f".join((self.title, str(self.url), self.text))
        return hashlib.sha256(payload.encode()).hexdigest()


class Chunk(_Frozen):
    id: str
    document_id: str
    title: str
    url: HttpUrl
    text: str
    chunk_index: int = Field(ge=0)
    content_hash: str

    @property
    def embedding_text(self) -> str:
        """Text sent for embedding: the title gives short chunks their context."""
        return f"{self.title}\n\n{self.text}"


class EmbeddedChunk(_Frozen):
    chunk: Chunk
    vector: list[float]
