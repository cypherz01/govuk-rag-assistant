"""FastAPI application entry point."""

import mimetypes
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from govuk_rag import __version__
from govuk_rag.answering.answerer import Answerer
from govuk_rag.answering.factory import build_answerer
from govuk_rag.config import Settings
from govuk_rag.models import ChatRequest, ChatResponse, HealthResponse
from govuk_rag.security import demo_key_guard

_WEB_DIR = Path(__file__).parent / "web"

# The chat page loads nothing but its own script and stylesheet, and can't be framed.
_PAGE_CSP = (
    "default-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'; object-src 'none'"
)

# Windows can map these to text/plain from the registry, which nosniff then refuses to run.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def create_app(settings: Settings | None = None, *, answerer: Answerer | None = None) -> FastAPI:
    """Build the application.

    Tests pass their own ``Settings`` and ``Answerer``; production reads the environment and
    wires the answerer to Azure. Without Azure endpoints the app still starts, but ``/chat``
    reports that it is unavailable.
    """
    resolved = settings if settings is not None else Settings()
    chat_answerer = answerer if answerer is not None else build_answerer(resolved)
    app = FastAPI(title=resolved.app_name, version=__version__)

    @app.middleware("http")
    async def security_headers(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def chat_page() -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        return FileResponse(_WEB_DIR / "index.html", headers={"Content-Security-Policy": _PAGE_CSP})

    app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")

    @app.get("/health", tags=["ops"])
    def health() -> HealthResponse:  # pyright: ignore[reportUnusedFunction]
        return HealthResponse(version=__version__, environment=resolved.environment)

    @app.post(
        "/chat",
        tags=["chat"],
        dependencies=[Depends(demo_key_guard(resolved.demo_key))],
        responses={
            status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid demo key"},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Not configured"},
        },
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
