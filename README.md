# GOV.UK RAG Assistant

An Azure-native assistant that answers staff questions about UK employee-rights guidance (leave,
sick pay, flexible working). Every answer cites its GOV.UK sources, and it says "I don't know" when
the documents don't cover a question.

> Work in progress: currently at **Milestone 1 (Foundation)**.

## Local development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                                   # install dependencies
uv run uvicorn govuk_rag.main:app --reload   # run the API on http://127.0.0.1:8000
```

### Checks

```sh
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run pyright               # type check (strict on src/govuk_rag)
uv run pytest                # tests
```

### Configuration

Settings come from environment variables prefixed `RAG_` (or a local `.env` file). See
[`.env.example`](.env.example).
