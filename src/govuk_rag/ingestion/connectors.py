"""Source connectors: where guidance documents are read from.

The pipeline depends only on :class:`SourceConnector`, so another source (for example
SharePoint via Microsoft Graph) can be added without changing ingestion.
"""

from collections.abc import Iterator
from typing import Protocol

from azure.storage.blob import ContainerClient
from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError

from govuk_rag.ingestion.models import SourceDocument


class SourceConnector(Protocol):
    def list_documents(self) -> Iterator[SourceDocument]:
        """Yield every document currently in the source."""
        ...


class BlobContainer(Protocol):
    """The two Blob Storage operations the connector needs."""

    def list_blob_names(self) -> Iterator[str]: ...

    def download_text(self, name: str) -> str: ...


class AzureBlobContainer:
    """Adapts an Azure ``ContainerClient`` to :class:`BlobContainer`."""

    def __init__(self, client: ContainerClient) -> None:
        self._client = client

    def list_blob_names(self) -> Iterator[str]:
        return iter(self._client.list_blob_names())

    def download_text(self, name: str) -> str:
        return self._client.download_blob(name, encoding="utf-8").readall()


class StoredDocument(BaseModel):
    """The JSON stored in each blob (written by ``govuk-rag-fetch``)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: HttpUrl
    text: str


class BlobSourceConnector:
    """Reads documents stored as JSON blobs; the document id is the blob name minus ``.json``."""

    _SUFFIX = ".json"

    def __init__(self, container: BlobContainer) -> None:
        self._container = container

    def list_documents(self) -> Iterator[SourceDocument]:
        names = sorted(n for n in self._container.list_blob_names() if n.endswith(self._SUFFIX))
        for name in names:
            try:
                stored = StoredDocument.model_validate_json(self._container.download_text(name))
            except ValidationError as error:
                msg = f"Blob {name!r} is not a valid document: {error}"
                raise ValueError(msg) from error
            yield SourceDocument(
                id=name.removesuffix(self._SUFFIX),
                title=stored.title,
                url=stored.url,
                text=stored.text,
            )
