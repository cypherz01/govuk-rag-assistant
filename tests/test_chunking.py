import re

import pytest

from govuk_rag.ingestion.chunking import chunk_document, split_text
from govuk_rag.ingestion.models import SourceDocument


def paragraph(label: str, length: int = 100) -> str:
    return (label + " " + "x" * length)[:length]


@pytest.mark.parametrize("text", ["", "   \n\n  "])
def test_blank_text_gives_no_chunks(text: str) -> None:
    assert split_text(text, max_chars=200, overlap_chars=50) == []


def test_short_text_is_a_single_chunk() -> None:
    assert split_text("One paragraph.\n\nAnother.", max_chars=200, overlap_chars=50) == [
        "One paragraph.\n\nAnother."
    ]


def test_packs_whole_paragraphs_without_exceeding_max() -> None:
    paragraphs = [paragraph(f"p{i}") for i in range(6)]

    chunks = split_text("\n\n".join(paragraphs), max_chars=250, overlap_chars=0)

    assert chunks == [
        f"{paragraphs[0]}\n\n{paragraphs[1]}",
        f"{paragraphs[2]}\n\n{paragraphs[3]}",
        f"{paragraphs[4]}\n\n{paragraphs[5]}",
    ]


def test_next_chunk_repeats_trailing_paragraph_as_overlap() -> None:
    paragraphs = [paragraph(f"p{i}") for i in range(4)]

    chunks = split_text("\n\n".join(paragraphs), max_chars=250, overlap_chars=120)

    assert chunks == [
        f"{paragraphs[0]}\n\n{paragraphs[1]}",
        f"{paragraphs[1]}\n\n{paragraphs[2]}",
        f"{paragraphs[2]}\n\n{paragraphs[3]}",
    ]


def test_overlap_is_skipped_when_trailing_paragraph_is_too_long() -> None:
    paragraphs = [paragraph(f"p{i}") for i in range(4)]

    chunks = split_text("\n\n".join(paragraphs), max_chars=250, overlap_chars=50)

    assert len(chunks) == 2


def test_oversized_paragraph_is_split_on_word_boundaries() -> None:
    words = [f"word{i}" for i in range(200)]

    chunks = split_text(" ".join(words), max_chars=100, overlap_chars=0)

    assert all(len(chunk) <= 100 for chunk in chunks)
    assert " ".join(chunks).split() == words


def test_collapses_runs_of_blank_lines() -> None:
    assert split_text("A\n\n\n\nB", max_chars=200, overlap_chars=0) == ["A\n\nB"]


def make_document(text: str = "Para one.\n\nPara two.") -> SourceDocument:
    return SourceDocument(
        id="holiday-entitlement-rights/entitlement",
        title="Holiday entitlement: Entitlement",
        url="https://www.gov.uk/holiday-entitlement-rights/entitlement",  # pyright: ignore[reportArgumentType]
        text=text,
    )


def test_chunk_document_carries_document_metadata() -> None:
    document = make_document()

    [chunk] = chunk_document(document, max_chars=200, overlap_chars=0)

    assert chunk.document_id == document.id
    assert chunk.title == document.title
    assert chunk.url == document.url
    assert chunk.content_hash == document.content_hash
    assert chunk.chunk_index == 0
    assert chunk.text == "Para one.\n\nPara two."


def test_chunk_ids_are_deterministic_unique_and_valid_search_keys() -> None:
    document = make_document("\n\n".join(paragraph(f"p{i}") for i in range(6)))

    first = chunk_document(document, max_chars=250, overlap_chars=0)
    second = chunk_document(document, max_chars=250, overlap_chars=0)

    ids = [chunk.id for chunk in first]
    assert ids == [chunk.id for chunk in second]
    assert len(set(ids)) == len(ids) == 3
    assert [chunk.chunk_index for chunk in first] == [0, 1, 2]
    assert all(re.fullmatch(r"[A-Za-z0-9_\-=]+", chunk_id) for chunk_id in ids)


def test_content_hash_changes_with_text() -> None:
    assert make_document("A").content_hash != make_document("B").content_hash
