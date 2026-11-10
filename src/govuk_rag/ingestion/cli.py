"""``govuk-rag-ingest``: sync the Blob Storage documents into the Azure AI Search index.

Safe to re-run: unchanged documents are skipped and no duplicates are created.
Authenticates with ``DefaultAzureCredential`` (``az login`` locally, managed identity in Azure).
"""

import argparse
import sys
from collections.abc import Sequence

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.blob import ContainerClient
from openai import AzureOpenAI

from govuk_rag.config import Settings
from govuk_rag.ingestion.connectors import AzureBlobContainer, BlobSourceConnector
from govuk_rag.ingestion.embeddings import AzureOpenAIEmbedder
from govuk_rag.ingestion.pipeline import ingest
from govuk_rag.search.index import AzureSearchChunkIndex

_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


def main(argv: Sequence[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Sync Blob Storage documents into the Azure AI Search index."
    ).parse_args(argv)
    settings = Settings()

    storage_url = settings.azure_storage_account_url
    search_url = settings.azure_search_endpoint
    openai_url = settings.azure_openai_endpoint
    if storage_url is None or search_url is None or openai_url is None:
        missing = [
            name
            for name, value in (
                ("RAG_AZURE_STORAGE_ACCOUNT_URL", storage_url),
                ("RAG_AZURE_SEARCH_ENDPOINT", search_url),
                ("RAG_AZURE_OPENAI_ENDPOINT", openai_url),
            )
            if value is None
        ]
        print(f"Missing required settings: {', '.join(missing)}", file=sys.stderr)
        return 2

    credential = DefaultAzureCredential()
    source = BlobSourceConnector(
        AzureBlobContainer(
            ContainerClient(
                account_url=str(storage_url),
                container_name=settings.blob_container_name,
                credential=credential,
            )
        )
    )
    embedder = AzureOpenAIEmbedder(
        AzureOpenAI(
            azure_endpoint=str(openai_url),
            api_version=settings.azure_openai_api_version,
            azure_ad_token_provider=get_bearer_token_provider(
                credential, _COGNITIVE_SERVICES_SCOPE
            ),
        ),
        deployment=settings.embedding_deployment,
    )
    index = AzureSearchChunkIndex(
        SearchIndexClient(str(search_url), credential),
        SearchClient(str(search_url), settings.search_index_name, credential),
        index_name=settings.search_index_name,
        embedding_dimensions=settings.embedding_dimensions,
    )

    report = ingest(
        source,
        embedder,
        index,
        max_chars=settings.chunk_max_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )
    print(report.model_dump_json(indent=2))
    return 0
