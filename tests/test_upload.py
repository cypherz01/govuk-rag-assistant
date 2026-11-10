import json
from pathlib import Path

import pytest

from govuk_rag.ingestion.upload import main, upload_directory


class FakeWritableContainer:
    def __init__(self) -> None:
        self.blobs: dict[str, str] = {}

    def upload_text(self, name: str, text: str) -> None:
        self.blobs[name] = text


def _write_document(directory: Path, name: str, title: str = "Holiday entitlement") -> str:
    content = json.dumps(
        {
            "title": title,
            "url": "https://www.gov.uk/holiday-entitlement-rights",
            "text": "5.6 weeks",
        }
    )
    (directory / name).write_text(content, encoding="utf-8")
    return content


def test_uploads_every_json_document_under_its_file_name(tmp_path: Path) -> None:
    first = _write_document(tmp_path, "holiday-entitlement-rights.json")
    second = _write_document(tmp_path, "statutory-sick-pay.json", title="Statutory Sick Pay")
    container = FakeWritableContainer()

    uploaded = upload_directory(tmp_path, container)

    assert uploaded == 2
    assert container.blobs == {
        "holiday-entitlement-rights.json": first,
        "statutory-sick-pay.json": second,
    }


def test_ignores_files_that_are_not_json(tmp_path: Path) -> None:
    _write_document(tmp_path, "holiday-entitlement-rights.json")
    (tmp_path / "README.txt").write_text("notes", encoding="utf-8")
    container = FakeWritableContainer()

    assert upload_directory(tmp_path, container) == 1
    assert list(container.blobs) == ["holiday-entitlement-rights.json"]


def test_rejects_an_invalid_document_before_uploading_anything(tmp_path: Path) -> None:
    _write_document(tmp_path, "a-valid.json")
    (tmp_path / "b-broken.json").write_text('{"title": "No url"}', encoding="utf-8")
    container = FakeWritableContainer()

    with pytest.raises(ValueError, match="b-broken.json"):
        upload_directory(tmp_path, container)

    assert container.blobs == {}


def test_rejects_a_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="govuk-rag-fetch"):
        upload_directory(tmp_path / "missing", FakeWritableContainer())


def test_cli_exits_with_usage_error_when_storage_is_not_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 2
    assert "RAG_AZURE_STORAGE_ACCOUNT_URL" in capsys.readouterr().err
