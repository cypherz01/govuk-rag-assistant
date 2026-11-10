# syntax=docker/dockerfile:1

# Build stage: install the locked dependencies and the app into a virtual environment.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# Runtime stage: just Python and the virtual environment, run as an unprivileged user.
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    RAG_ENVIRONMENT=prod
USER app
WORKDIR /home/app
EXPOSE 8000
# Container Apps terminates TLS at its ingress and forwards the original scheme and client.
CMD ["uvicorn", "govuk_rag.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
