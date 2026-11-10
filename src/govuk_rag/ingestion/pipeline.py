"""The re-runnable ingestion pipeline."""

from pydantic import BaseModel, Field

from govuk_rag.ingestion.chunking import chunk_document
from govuk_rag.ingestion.connectors import SourceConnector
from govuk_rag.ingestion.embeddings import Embedder
from govuk_rag.ingestion.models import EmbeddedChunk
from govuk_rag.search.index import ChunkIndex


class IngestionReport(BaseModel):
    added: list[str] = Field(default_factory=list[str])
    updated: list[str] = Field(default_factory=list[str])
    unchanged: list[str] = Field(default_factory=list[str])
    removed: list[str] = Field(default_factory=list[str])
    chunks_indexed: int = 0


def ingest(
    source: SourceConnector,
    embedder: Embedder,
    index: ChunkIndex,
    *,
    max_chars: int,
    overlap_chars: int,
) -> IngestionReport:
    """Bring the index in line with the source.

    Documents are compared by content hash: unchanged ones are skipped (no embedding cost),
    changed ones have their old chunks replaced, and ones no longer in the source are removed.
    Chunk ids are deterministic, so running this repeatedly never creates duplicates.
    """
    index.ensure_exists()
    indexed_hashes = index.document_hashes()
    report = IngestionReport()
    seen: set[str] = set()

    for document in source.list_documents():
        seen.add(document.id)
        previous_hash = indexed_hashes.get(document.id)
        if previous_hash == document.content_hash:
            report.unchanged.append(document.id)
            continue

        chunks = chunk_document(document, max_chars=max_chars, overlap_chars=overlap_chars)
        vectors = embedder.embed([chunk.embedding_text for chunk in chunks])
        if previous_hash is None:
            report.added.append(document.id)
        else:
            index.delete_documents([document.id])
            report.updated.append(document.id)
        index.upsert(
            [EmbeddedChunk(chunk=c, vector=v) for c, v in zip(chunks, vectors, strict=True)]
        )
        report.chunks_indexed += len(chunks)

    report.removed = sorted(set(indexed_hashes) - seen)
    if report.removed:
        index.delete_documents(report.removed)
    return report
