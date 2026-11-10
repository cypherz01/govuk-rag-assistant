"""FastAPI application entry point."""

from fastapi import FastAPI

from govuk_rag import __version__
from govuk_rag.config import Settings
from govuk_rag.models import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Tests pass their own ``Settings``; production reads the env."""
    resolved = settings if settings is not None else Settings()
    app = FastAPI(title=resolved.app_name, version=__version__)

    @app.get("/health", tags=["ops"])
    def health() -> HealthResponse:  # pyright: ignore[reportUnusedFunction]
        return HealthResponse(version=__version__, environment=resolved.environment)

    return app


app = create_app()
