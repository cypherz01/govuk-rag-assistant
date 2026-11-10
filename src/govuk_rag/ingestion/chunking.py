"""Paragraph-aware text chunking."""

import hashlib
import re

from govuk_rag.ingestion.models import Chunk, SourceDocument

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def split_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    """Split text into chunks of at most ``max_chars``, keeping paragraphs whole where possible.

    Consecutive chunks share trailing paragraphs totalling at most ``overlap_chars``, so an
    answer that spans a chunk boundary is still retrievable.
    """
    paragraphs = [
        piece
        for raw in _PARAGRAPH_BREAK.split(text)
        if (stripped := raw.strip())
        for piece in _split_long(stripped, max_chars)
    ]

    chunks: list[list[str]] = []
    current: list[str] = []
    has_new = False  # does `current` contain a paragraph not already emitted?
    for paragraph in paragraphs:
        if current and _joined_length([*current, paragraph]) > max_chars:
            if has_new:
                chunks.append(current)
            current = _overlap_tail(current, overlap_chars)
            if _joined_length([*current, paragraph]) > max_chars:
                current = []
        current.append(paragraph)
        has_new = True
    if has_new:
        chunks.append(current)

    return ["\n\n".join(chunk) for chunk in chunks]


def chunk_document(document: SourceDocument, *, max_chars: int, overlap_chars: int) -> list[Chunk]:
    texts = split_text(document.text, max_chars=max_chars, overlap_chars=overlap_chars)
    id_prefix = hashlib.sha1(document.id.encode(), usedforsecurity=False).hexdigest()[:16]
    return [
        Chunk(
            id=f"{id_prefix}-{index:04d}",
            document_id=document.id,
            title=document.title,
            url=document.url,
            text=text,
            chunk_index=index,
            content_hash=document.content_hash,
        )
        for index, text in enumerate(texts)
    ]


def _joined_length(paragraphs: list[str]) -> int:
    return sum(len(p) for p in paragraphs) + 2 * (len(paragraphs) - 1)


def _overlap_tail(paragraphs: list[str], overlap_chars: int) -> list[str]:
    tail: list[str] = []
    for paragraph in reversed(paragraphs):
        if _joined_length([paragraph, *tail]) > overlap_chars:
            break
        tail.insert(0, paragraph)
    return tail


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    """Break a paragraph longer than ``max_chars`` on whitespace (or mid-word as a last resort)."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    words = paragraph.split()
    pieces: list[str] = []
    current = ""
    for word in words:
        while len(word) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:max_chars])
            word = word[max_chars:]  # noqa: PLW2901
        candidate = f"{current} {word}" if current else word
        if len(candidate) > max_chars:
            pieces.append(current)
            candidate = word
        current = candidate
    if current:
        pieces.append(current)
    return pieces
