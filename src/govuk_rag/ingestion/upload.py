"""``govuk-rag-upload``: upload the fetched JSON documents to the Blob Storage container.

Every file is validated before anything is uploaded, so a bad file never leaves the container
half-updated. Existing blobs with the same name are overwritten; ``govuk-rag-ingest`` then
re-indexes only the documents whose content changed.
Authenticates with ``DefaultAzureCredential`` (``az login``/``azd auth login`` locally).
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient, ContentSettings
from pydantic import ValidationError

from govuk_rag.config import Settings
from govuk_rag.ingestion.connectors import StoredDocument


class WritableBlobContainer(Protocol):
    def upload_text(self, name: str, text: str) -> None:
        """Create or overwrite the blob ``name`` with ``text``."""
        ...


class AzureWritableBlobContainer:
    """Adapts an Azure ``ContainerClient`` to :class:`WritableBlobContainer`."""

    def __init__(self, client: ContainerClient) -> None:
        self._client = client

    def upload_text(self, name: str, text: str) -> None:
        self._client.upload_blob(
            name,
            text.encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )


def upload_directory(directory: Path, container: WritableBlobContainer) -> int:
    """Upload every ``*.json`` document in ``directory``; return how many were uploaded."""
    if not directory.is_dir():
        msg = f"{directory} does not exist: run govuk-rag-fetch first"
        raise FileNotFoundError(msg)

    documents: list[tuple[str, str]] = []
    for path in sorted(directory.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        try:
            StoredDocument.model_validate_json(text)
        except ValidationError as error:
            msg = f"{path.name} is not a valid document: {error}"
            raise ValueError(msg) from error
        documents.append((path.name, text))

    for name, text in documents:
        container.upload_text(name, text)
    return len(documents)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload fetched documents to Blob Storage.")
    parser.add_argument("--source", type=Path, default=Path("data/govuk"))
    args = parser.parse_args(argv)
    source: Path = args.source
    settings = Settings()

    storage_url = settings.azure_storage_account_url
    if storage_url is None:
        print("Missing required settings: RAG_AZURE_STORAGE_ACCOUNT_URL", file=sys.stderr)
        return 2

    container = AzureWritableBlobContainer(
        ContainerClient(
            account_url=str(storage_url),
            container_name=settings.blob_container_name,
            credential=DefaultAzureCredential(),
        )
    )
    uploaded = upload_directory(source, container)
    print(f"Uploaded {uploaded} documents to {settings.blob_container_name}")
    return 0
