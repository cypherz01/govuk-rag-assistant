import json
from collections.abc import Iterator

import pytest

from govuk_rag.ingestion.connectors import BlobSourceConnector


class FakeContainer:
    def __init__(self, blobs: dict[str, str]) -> None:
        self.blobs = blobs

    def list_blob_names(self) -> Iterator[str]:
        return iter(self.blobs)

    def download_text(self, name: str) -> str:
        return self.blobs[name]


def blob(title: str, url: str, text: str) -> str:
    return json.dumps({"title": title, "url": url, "text": text})


def test_reads_json_blobs_as_documents_in_name_order() -> None:
    container = FakeContainer(
        {
            "statutory-sick-pay/overview.json": blob(
                "Statutory Sick Pay: Overview",
                "https://www.gov.uk/statutory-sick-pay/overview",
                "You can get SSP if you're too ill to work.",
            ),
            "flexible-working/overview.json": blob(
                "Flexible working: Overview",
                "https://www.gov.uk/flexible-working/overview",
                "Flexible working suits an employee's needs.",
            ),
        }
    )

    documents = list(BlobSourceConnector(container).list_documents())

    assert [d.id for d in documents] == ["flexible-working/overview", "statutory-sick-pay/overview"]
    assert documents[1].title == "Statutory Sick Pay: Overview"
    assert str(documents[1].url) == "https://www.gov.uk/statutory-sick-pay/overview"
    assert documents[1].text == "You can get SSP if you're too ill to work."


def test_ignores_blobs_that_are_not_json() -> None:
    container = FakeContainer(
        {"README.txt": "notes", "a.json": blob("A", "https://www.gov.uk/a", "a")}
    )

    assert [d.id for d in BlobSourceConnector(container).list_documents()] == ["a"]


def test_invalid_blob_error_names_the_blob() -> None:
    container = FakeContainer({"broken.json": json.dumps({"title": "No url or text"})})

    with pytest.raises(ValueError, match=r"broken\.json"):
        list(BlobSourceConnector(container).list_documents())
