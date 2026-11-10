from collections.abc import Iterator
from typing import Any

from govuk_rag.ingestion.models import Chunk, EmbeddedChunk
from govuk_rag.search.index import EDM_VECTOR, AzureSearchChunkIndex, build_index_definition


def test_index_definition_supports_hybrid_search() -> None:
    index = build_index_definition("govuk-guidance", embedding_dimensions=1536)
    fields = {f.name: f for f in index.fields}

    assert index.name == "govuk-guidance"
    assert fields["id"].key
    assert fields["document_id"].filterable
    assert fields["content"].searchable
    assert fields["title"].searchable
    assert fields["chunk_index"].filterable
    vector = fields["content_vector"]
    assert vector.type == EDM_VECTOR
    assert vector.vector_search_dimensions == 1536
    assert index.vector_search is not None
    assert [p.name for p in index.vector_search.profiles or []] == [
        vector.vector_search_profile_name
    ]


class FakeSearchClient:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.search_calls: list[dict[str, Any]] = []
        self.uploaded: list[dict[str, Any]] = []
        self.deleted: list[dict[str, Any]] = []

    def search(self, search_text: str, **kwargs: Any) -> Iterator[dict[str, Any]]:  # noqa: ANN401
        self.search_calls.append({"search_text": search_text, **kwargs})
        return iter(self.results)

    def merge_or_upload_documents(self, documents: list[dict[str, Any]]) -> None:
        self.uploaded.extend(documents)

    def delete_documents(self, documents: list[dict[str, Any]]) -> None:
        self.deleted.extend(documents)


class FakeIndexClient:
    def __init__(self) -> None:
        self.created: list[Any] = []

    def create_or_update_index(self, index: Any) -> None:  # noqa: ANN401
        self.created.append(index)


def make_index(search: FakeSearchClient) -> tuple[AzureSearchChunkIndex, FakeIndexClient]:
    index_client = FakeIndexClient()
    return (
        AzureSearchChunkIndex(index_client, search, index_name="idx", embedding_dimensions=3),
        index_client,
    )


def test_ensure_exists_creates_or_updates_the_index() -> None:
    chunk_index, index_client = make_index(FakeSearchClient([]))

    chunk_index.ensure_exists()

    assert [i.name for i in index_client.created] == ["idx"]


def test_document_hashes_reads_first_chunk_of_each_document() -> None:
    search = FakeSearchClient(
        [
            {"document_id": "a", "content_hash": "h1"},
            {"document_id": "b", "content_hash": "h2"},
        ]
    )
    chunk_index, _ = make_index(search)

    assert chunk_index.document_hashes() == {"a": "h1", "b": "h2"}
    assert search.search_calls[0]["filter"] == "chunk_index eq 0"


def test_upsert_maps_chunks_to_search_documents() -> None:
    search = FakeSearchClient([])
    chunk_index, _ = make_index(search)
    chunk = Chunk(
        id="abc-0000",
        document_id="sick-pay",
        title="Sick pay",
        url="https://www.gov.uk/statutory-sick-pay",  # pyright: ignore[reportArgumentType]
        text="SSP text",
        chunk_index=0,
        content_hash="h",
    )

    chunk_index.upsert([EmbeddedChunk(chunk=chunk, vector=[0.1, 0.2, 0.3])])

    assert search.uploaded == [
        {
            "id": "abc-0000",
            "document_id": "sick-pay",
            "title": "Sick pay",
            "url": "https://www.gov.uk/statutory-sick-pay",
            "content": "SSP text",
            "chunk_index": 0,
            "content_hash": "h",
            "content_vector": [0.1, 0.2, 0.3],
        }
    ]


def test_delete_documents_removes_all_their_chunks_and_escapes_quotes() -> None:
    search = FakeSearchClient([{"id": "c1"}, {"id": "c2"}])
    chunk_index, _ = make_index(search)

    chunk_index.delete_documents(["employer's-guide"])

    assert search.search_calls[0]["filter"] == "document_id eq 'employer''s-guide'"
    assert search.deleted == [{"id": "c1"}, {"id": "c2"}]


def test_delete_documents_with_nothing_to_delete_makes_no_delete_call() -> None:
    search = FakeSearchClient([])
    chunk_index, _ = make_index(search)

    chunk_index.delete_documents(["gone"])

    assert search.deleted == []
