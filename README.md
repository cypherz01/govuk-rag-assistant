# GOV.UK RAG Assistant

An Azure-native assistant that answers staff questions about UK employee-rights guidance (leave,
sick pay, flexible working). Every answer cites its GOV.UK sources, and it says "I don't know" when
the documents don't cover a question.

> Work in progress: currently at **Milestone 4 (Chat UI and access)**.

## Local development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                                   # install dependencies
uv run uvicorn govuk_rag.main:app --reload   # chat page and API on http://127.0.0.1:8000
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

## Ingestion

Guidance flows GOV.UK → Blob Storage → chunk + embed → Azure AI Search.

1. **Fetch** the pages listed in [`data/govuk_pages.txt`](data/govuk_pages.txt) from the GOV.UK
   Content API. Multi-part guides become one document per part, so citations link to the exact
   section.

   ```sh
   uv run govuk-rag-fetch            # writes JSON documents to data/govuk/
   ```

2. **Upload** them to the Blob container (signed in with `az login`, no keys):

   ```sh
   az storage blob upload-batch --auth-mode login --overwrite \
     --account-name <storage-account> --destination govuk-guidance --source data/govuk
   ```

3. **Index** them. This creates the search index if needed, then syncs it with the container:

   ```sh
   uv run govuk-rag-ingest
   ```

   Re-running is safe. Unchanged documents are skipped and not re-embedded. Changed documents
   have their chunks replaced, and documents deleted from the container are removed from the
   index. Chunk ids are deterministic, so re-running never creates duplicates.

Ingestion signs in with `DefaultAzureCredential`. Your identity, or the app's managed identity,
needs these roles:

- **Storage Blob Data Reader** on the storage account.
- **Search Index Data Contributor** and **Search Service Contributor** on the search service.
- **Cognitive Services OpenAI User** on the OpenAI resource.

Other data sources plug in by implementing `SourceConnector` (`src/govuk_rag/ingestion/connectors.py`).

## Answering

`POST /chat` takes `{"question": "..."}` and returns an answer with citations, or a fixed
"I don't know" reply:

1. **Retrieve.** One hybrid (keyword + vector) query to Azure AI Search returns the top
   `RAG_RETRIEVAL_TOP_K` chunks. Each chunk is scored by the cosine similarity between the question
   and the chunk. Hybrid search's own score only reflects rank, so a threshold can't use it.
2. **Gate.** Chunks below `RAG_RELEVANCE_THRESHOLD` are dropped. If none are left, the service
   answers "I don't know" without calling the model.
3. **Answer.** The model (`RAG_CHAT_DEPLOYMENT`, capped at `RAG_MAX_OUTPUT_TOKENS`) is told to
   answer only from the numbered sources, to cite them as `[1]`, and to reply `NO_ANSWER` when they
   don't answer the question. `NO_ANSWER` becomes the same "I don't know" reply.
4. **Cite.** Citations list the sources the answer cites, renumbered in order of use, each with
   its page title, GOV.UK link and a snippet.

`/chat` needs `RAG_AZURE_SEARCH_ENDPOINT` and `RAG_AZURE_OPENAI_ENDPOINT`. Without them it returns
HTTP 503. Your identity needs **Search Index Data Reader** on the search service and
**Cognitive Services OpenAI User** on the OpenAI resource.

## Chat page and access

The chat page is served at `/`. It's a single HTML page with its own script and stylesheet, and no
build step.

`/chat` is protected by a shared demo key, sent in the `X-Demo-Key` header:

- Set it with `RAG_DEMO_KEY`. Locally, put it in `.env`. When deployed, it's a Container Apps
  secret.
- Requests with a missing or wrong key get HTTP 401. If no key is configured, `/chat` rejects
  every request with HTTP 503, so a missing secret never leaves it open.
- The page asks for the key and keeps it in the browser's local storage. To share a link that
  fills the key in, use `https://<host>/#key=<demo-key>`. The part after `#` is never sent to
  the server, so the key stays out of server logs, and the page removes it from the address bar.
- `/health` and the page itself need no key.

The page loads nothing from other sites and has no inline code, so it is served with a strict
Content-Security-Policy. Answers are added as plain text, never as HTML.

GOV.UK content is © Crown copyright, used under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
