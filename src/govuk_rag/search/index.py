"""The chunk index: an Azure AI Search index supporting hybrid (keyword + vector) search."""

from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, Protocol

from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchIndex,
    VectorSearch,
    VectorSearchProfile,
)

from govuk_rag.ingestion.models import EmbeddedChunk

EDM_VECTOR = "Collection(Edm.Single)"
_EDM_STRING = "Edm.String"
_VECTOR_PROFILE = "content-vector-profile"
_HNSW_CONFIG = "content-hnsw"


class ChunkIndex(Protocol):
    """Where embedded chunks are stored. Implemented by Azure AI Search; faked in tests."""

    def ensure_exists(self) -> None: ...

    def document_hashes(self) -> dict[str, str]:
        """Map each indexed document id to the content hash it was indexed with."""
        ...

    def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None: ...

    def delete_documents(self, document_ids: Iterable[str]) -> None:
        """Remove every chunk belonging to the given documents."""
        ...


class SearchDocumentsClient(Protocol):
    """The slice of ``azure.search.documents.SearchClient`` used here."""

    def search(
        self,
        search_text: str,
        *,
        filter: str,  # noqa: A002 - matches the SDK's keyword name
        select: list[str],
        order_by: list[str] | None = None,
    ) -> Iterator[Mapping[str, Any]]: ...

    def merge_or_upload_documents(self, documents: list[dict[str, Any]]) -> object: ...

    def delete_documents(self, documents: list[dict[str, Any]]) -> object: ...


class SearchIndexAdminClient(Protocol):
    """The slice of ``azure.search.documents.indexes.SearchIndexClient`` used here."""

    def create_or_update_index(self, index: SearchIndex) -> object: ...


def _field(name: str, edm_type: str, **attributes: bool) -> SearchField:
    """A field with the given attributes (key, searchable, filterable, sortable) switched on."""
    return SearchField(name=name, type=edm_type, **attributes)


def build_index_definition(name: str, *, embedding_dimensions: int) -> SearchIndex:
    # EDM type names are used directly: the SDK's SearchFieldDataType enum is untyped.
    return SearchIndex(
        name=name,
        fields=[
            _field("id", _EDM_STRING, key=True),
            _field("document_id", _EDM_STRING, filterable=True, sortable=True),
            _field("title", _EDM_STRING, searchable=True),
            _field("url", _EDM_STRING),
            _field("content", _EDM_STRING, searchable=True),
            _field("chunk_index", "Edm.Int32", filterable=True),
            _field("content_hash", _EDM_STRING),
            SearchField(
                name="content_vector",
                type=EDM_VECTOR,
                searchable=True,
                retrievable=True,  # retrieval reads it back to score cosine relevance
                stored=True,
                vector_search_dimensions=embedding_dimensions,
                vector_search_profile_name=_VECTOR_PROFILE,
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name=_HNSW_CONFIG)],
            profiles=[
                VectorSearchProfile(name=_VECTOR_PROFILE, algorithm_configuration_name=_HNSW_CONFIG)
            ],
        ),
    )


class AzureSearchChunkIndex:
    def __init__(
        self,
        index_client: SearchIndexAdminClient,
        search_client: SearchDocumentsClient,
        *,
        index_name: str,
        embedding_dimensions: int,
    ) -> None:
        self._index_client = index_client
        self._search_client = search_client
        self._index_name = index_name
        self._embedding_dimensions = embedding_dimensions

    def ensure_exists(self) -> None:
        self._index_client.create_or_update_index(
            build_index_definition(
                self._index_name, embedding_dimensions=self._embedding_dimensions
            )
        )

    def document_hashes(self) -> dict[str, str]:
        # Every chunk carries its document's hash, so reading chunk 0 gives one row per document.
        # "*" scores every row the same, so sort to keep the pages stable: unsorted, Azure's pages
        # can repeat some rows and skip others.
        results = self._search_client.search(
            "*",
            filter="chunk_index eq 0",
            select=["document_id", "content_hash"],
            order_by=["document_id"],
        )
        return {str(row["document_id"]): str(row["content_hash"]) for row in results}

    def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None:
        if chunks:
            self._search_client.merge_or_upload_documents([_to_search_document(c) for c in chunks])

    def delete_documents(self, document_ids: Iterable[str]) -> None:
        for document_id in document_ids:
            results = self._search_client.search(
                "*", filter=f"document_id eq {_odata_string(document_id)}", select=["id"]
            )
            keys = [{"id": str(row["id"])} for row in results]
            if keys:
                self._search_client.delete_documents(keys)


def _to_search_document(embedded: EmbeddedChunk) -> dict[str, Any]:
    chunk = embedded.chunk
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "title": chunk.title,
        "url": str(chunk.url),
        "content": chunk.text,
        "chunk_index": chunk.chunk_index,
        "content_hash": chunk.content_hash,
        "content_vector": embedded.vector,
    }


def _odata_string(value: str) -> str:
    """Quote a value for an OData filter, escaping single quotes by doubling them."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"
