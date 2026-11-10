"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException, status

from govuk_rag import __version__
from govuk_rag.answering.answerer import Answerer
from govuk_rag.answering.factory import build_answerer
from govuk_rag.config import Settings
from govuk_rag.models import ChatRequest, ChatResponse, HealthResponse


def create_app(settings: Settings | None = None, *, answerer: Answerer | None = None) -> FastAPI:
    """Build the application.

    Tests pass their own ``Settings`` and ``Answerer``; production reads the environment and
    wires the answerer to Azure. Without Azure endpoints the app still starts, but ``/chat``
    reports that it is unavailable.
    """
    resolved = settings if settings is not None else Settings()
    chat_answerer = answerer if answerer is not None else build_answerer(resolved)
    app = FastAPI(title=resolved.app_name, version=__version__)

    @app.get("/health", tags=["ops"])
    def health() -> HealthResponse:  # pyright: ignore[reportUnusedFunction]
        return HealthResponse(version=__version__, environment=resolved.environment)

    @app.post(
        "/chat",
        tags=["chat"],
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Not configured"}},
    )
    def chat(request: ChatRequest) -> ChatResponse:  # pyright: ignore[reportUnusedFunction]
        """Answer a question from the GOV.UK guidance, citing sources, or say "I don't know"."""
        if chat_answerer is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Answering is not configured: set the Azure Search and OpenAI endpoints.",
            )
        return chat_answerer.answer(request.question)

    return app


app = create_app()
