from govuk_rag.ingestion.models import SourceDocument
from govuk_rag.ingestion.pipeline import ingest
from tests.fakes import FakeChunkIndex, FakeEmbedder, FakeSource

MAX_CHARS = 250
OVERLAP = 0


def document(doc_id: str, text: str) -> SourceDocument:
    return SourceDocument(
        id=doc_id,
        title=f"Title {doc_id}",
        url=f"https://www.gov.uk/{doc_id}",  # pyright: ignore[reportArgumentType]
        text=text,
    )


LONG_TEXT = "\n\n".join(("p" + str(i) + " " + "x" * 100)[:100] for i in range(6))


def run(source: FakeSource, embedder: FakeEmbedder, index: FakeChunkIndex):  # noqa: ANN201
    return ingest(source, embedder, index, max_chars=MAX_CHARS, overlap_chars=OVERLAP)


def test_first_run_indexes_every_document() -> None:
    source = FakeSource([document("sick-pay", LONG_TEXT), document("flexible-working", "Short.")])
    embedder, index = FakeEmbedder(), FakeChunkIndex()

    report = run(source, embedder, index)

    assert index.ensure_exists_calls == 1
    assert sorted(report.added) == ["flexible-working", "sick-pay"]
    assert report.updated == report.unchanged == report.removed == []
    assert report.chunks_indexed == 4
    assert len(index.chunks) == 4


def test_embeds_chunk_text_prefixed_with_title() -> None:
    embedder, index = FakeEmbedder(), FakeChunkIndex()

    run(FakeSource([document("sick-pay", "Statutory Sick Pay is paid by employers.")]), embedder, index)

    assert embedder.texts_embedded == ["Title sick-pay\n\nStatutory Sick Pay is paid by employers."]
    [stored] = index.chunks.values()
    assert stored.vector == [float(len(embedder.texts_embedded[0])), 1.0, 0.0]


def test_rerun_with_unchanged_documents_creates_no_duplicates_and_skips_embedding() -> None:
    source = FakeSource([document("sick-pay", LONG_TEXT), document("flexible-working", "Short.")])
    embedder, index = FakeEmbedder(), FakeChunkIndex()
    run(source, embedder, index)
    chunks_after_first_run = dict(index.chunks)
    embedder.calls.clear()

    report = run(source, embedder, index)

    assert index.chunks == chunks_after_first_run
    assert embedder.calls == []
    assert sorted(report.unchanged) == ["flexible-working", "sick-pay"]
    assert report.added == report.updated == report.removed == []
    assert report.chunks_indexed == 0


def test_changed_document_is_reindexed_and_stale_chunks_removed() -> None:
    embedder, index = FakeEmbedder(), FakeChunkIndex()
    run(FakeSource([document("sick-pay", LONG_TEXT)]), embedder, index)
    assert len(index.chunk_ids_for("sick-pay")) == 3

    report = run(FakeSource([document("sick-pay", "Rewritten and much shorter.")]), embedder, index)

    assert report.updated == ["sick-pay"]
    [remaining] = index.chunks.values()
    assert remaining.chunk.text == "Rewritten and much shorter."


def test_document_removed_from_source_is_removed_from_index() -> None:
    embedder, index = FakeEmbedder(), FakeChunkIndex()
    run(FakeSource([document("sick-pay", "A."), document("old-page", "B.")]), embedder, index)

    report = run(FakeSource([document("sick-pay", "A.")]), embedder, index)

    assert report.removed == ["old-page"]
    assert index.chunk_ids_for("old-page") == set()
    assert index.chunk_ids_for("sick-pay") != set()
