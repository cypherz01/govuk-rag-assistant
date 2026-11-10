"""Fetch guidance pages from the GOV.UK Content API and save them as JSON documents.

Content is Crown copyright, published under the Open Government Licence v3.0.
The saved files are uploaded to Blob Storage and read by ``BlobSourceConnector``.
"""

import argparse
import logging
import time
from collections.abc import Callable, Iterable, Sequence
from html.parser import HTMLParser
from pathlib import Path
from typing import override

import httpx
from pydantic import BaseModel, ConfigDict

from govuk_rag.ingestion.connectors import StoredDocument
from govuk_rag.ingestion.models import SourceDocument

logger = logging.getLogger(__name__)

GOVUK_BASE_URL = "https://www.gov.uk"
CONTENT_API_URL = f"{GOVUK_BASE_URL}/api/content"

_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "div", "blockquote", "table"}
_LIST_TAGS = {"ul", "ol"}
_SKIP_TAGS = {"script", "style"}
_CELL_TAGS = {"td", "th"}


class _TextExtractor(HTMLParser):
    """Converts GOV.UK body HTML into plain text with paragraphs separated by blank lines."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[list[str]] = []
        self._lines: list[str] = []
        self._fragments: list[str] = []
        self._prefix = ""
        self._list_depth = 0
        self._skip_depth = 0
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _LIST_TAGS:
            if self._list_depth == 0:
                self._end_block()
            self._list_depth += 1
        elif tag == "li":
            self._flush_line()
            self._prefix = "- "
        elif tag == "tr":
            self._flush_line()
            self._row = []
        elif tag in _CELL_TAGS:
            self._cell = []
        elif tag == "br":
            self._flush_line()
        elif tag in _BLOCK_TAGS and self._list_depth == 0:
            self._end_block()

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _LIST_TAGS:
            self._list_depth = max(0, self._list_depth - 1)
            if self._list_depth == 0:
                self._end_block()
        elif tag == "li":
            self._flush_line()
        elif tag in _CELL_TAGS:
            if self._row is not None and self._cell is not None:
                self._row.append(_normalise("".join(self._cell)))
            self._cell = None
        elif tag == "tr":
            if self._row:
                self._lines.append(" | ".join(self._row))
            self._row = None
        elif tag in _BLOCK_TAGS and self._list_depth == 0:
            self._end_block()

    @override
    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._cell is not None:
            self._cell.append(data)
        else:
            self._fragments.append(data)

    @override
    def close(self) -> None:
        super().close()
        self._end_block()

    def _flush_line(self) -> None:
        text = _normalise("".join(self._fragments))
        if text:
            self._lines.append(self._prefix + text)
        self._fragments = []
        self._prefix = ""

    def _end_block(self) -> None:
        self._flush_line()
        if self._lines:
            self.blocks.append(self._lines)
        self._lines = []


def _normalise(text: str) -> str:
    return " ".join(text.split())


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return "\n\n".join("\n".join(lines) for lines in extractor.blocks)


class _Part(BaseModel):
    slug: str
    title: str
    body: str = ""


class _Details(BaseModel):
    body: str | None = None
    parts: list[_Part] | None = None


class _ContentItem(BaseModel):
    """The fields used from a GOV.UK Content API response."""

    model_config = ConfigDict(extra="ignore")

    title: str | None  # null for redirect and gone stubs
    base_path: str
    details: _Details


def documents_from_content_item(item: object) -> list[SourceDocument]:
    """Turn a Content API item into documents: one per guide part, or one for a single page.

    Items without content (such as redirects) give no documents.
    """
    content = _ContentItem.model_validate(item)
    if content.title is None:
        return []
    base_id = content.base_path.strip("/")
    candidates: list[tuple[str, str, str]] = []  # (id, title, html)
    if content.details.parts:
        candidates = [
            (f"{base_id}/{part.slug}", f"{content.title}: {part.title}", part.body)
            for part in content.details.parts
        ]
    elif content.details.body:
        candidates = [(base_id, content.title, content.details.body)]

    documents: list[SourceDocument] = []
    for doc_id, title, html in candidates:
        text = html_to_text(html)
        if text:
            documents.append(
                SourceDocument.model_validate(
                    {
                        "id": doc_id,
                        "title": title,
                        "url": f"{GOVUK_BASE_URL}/{doc_id}",
                        "text": text,
                    }
                )
            )
    return documents


def fetch_pages(paths: Iterable[str], get_json: Callable[[str], object], out_dir: Path) -> int:
    """Fetch each GOV.UK path and write its documents to ``out_dir``. Returns files written."""
    written = 0
    for path in paths:
        documents = documents_from_content_item(get_json(f"{CONTENT_API_URL}{path}"))
        if not documents:
            logger.warning("%s has no content (it may be a redirect); skipped", path)
        for document in documents:
            target = out_dir / f"{document.id}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            stored = StoredDocument(title=document.title, url=document.url, text=document.text)
            target.write_text(stored.model_dump_json(indent=2) + "\n", encoding="utf-8")
            written += 1
    return written


def read_page_list(path: Path) -> list[str]:
    """Read GOV.UK paths, one per line; blank lines and ``#`` comments are ignored."""
    paths: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            paths.append("/" + stripped.lstrip("/"))
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch GOV.UK guidance pages as JSON documents.")
    parser.add_argument("--pages", type=Path, default=Path("data/govuk_pages.txt"))
    parser.add_argument("--out", type=Path, default=Path("data/govuk"))
    args = parser.parse_args(argv)
    pages: Path = args.pages
    out_dir: Path = args.out

    with httpx.Client(
        headers={"User-Agent": "govuk-rag-assistant (portfolio project)"}, timeout=30
    ) as client:

        def get_json(url: str) -> object:
            time.sleep(0.2)  # be polite to the Content API
            response = client.get(url)
            response.raise_for_status()
            return response.json()

        written = fetch_pages(read_page_list(pages), get_json, out_dir)

    print(f"Wrote {written} documents to {out_dir}")
    return 0
