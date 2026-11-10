"""Application configuration, loaded from ``RAG_``-prefixed environment variables."""

from typing import Literal

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "dev", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime settings.

    No secrets live here: Azure services are reached with managed identity, so only
    endpoints are configured.
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
    azure_openai_endpoint: HttpUrl | None = None
    azure_search_endpoint: HttpUrl | None = None
