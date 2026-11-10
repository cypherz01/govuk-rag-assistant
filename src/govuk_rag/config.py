"""Application configuration, loaded from ``RAG_``-prefixed environment variables."""

from typing import Literal, Self

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "dev", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime settings.

    No secrets live here: Azure services are reached with managed identity, so only
    endpoints and resource names are configured.
    """

    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "GOV.UK RAG Assistant"
    environment: Environment = "local"
    log_level: LogLevel = "INFO"

    # Azure endpoints (unset locally until resources exist).
    azure_openai_endpoint: HttpUrl | None = None
    azure_search_endpoint: HttpUrl | None = None
    azure_storage_account_url: HttpUrl | None = None

    # Ingestion
    azure_openai_api_version: str = "2024-10-21"
    blob_container_name: str = "govuk-guidance"
    search_index_name: str = "govuk-guidance"
    embedding_deployment: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, gt=0)
    chunk_max_chars: int = Field(default=1500, gt=0)
    chunk_overlap_chars: int = Field(default=200, ge=0)

    # Answering
    chat_deployment: str = "gpt-4o-mini"
    retrieval_top_k: int = Field(default=5, gt=0)
    # Minimum cosine similarity between question and chunk for the chunk to count as relevant.
    # Provisional until hand-tuned against the live index (see the relevance-threshold ADR).
    relevance_threshold: float = Field(default=0.35, ge=-1.0, le=1.0)
    max_output_tokens: int = Field(default=500, gt=0)

    @model_validator(mode="after")
    def _overlap_smaller_than_chunk(self) -> Self:
        if self.chunk_overlap_chars >= self.chunk_max_chars:
            msg = "chunk_overlap_chars must be smaller than chunk_max_chars"
            raise ValueError(msg)
        return self
