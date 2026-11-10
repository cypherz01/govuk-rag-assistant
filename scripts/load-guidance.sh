#!/bin/sh
# Fetch the GOV.UK guidance, upload it to Blob Storage and index it in Azure AI Search.
# Run by azd after provisioning; azd supplies the RAG_* endpoints from the Bicep outputs.
# Re-runnable: unchanged documents are not re-uploaded into the index or re-embedded.
set -eu

if [ "${SKIP_GUIDANCE_LOAD:-false}" = "true" ]; then
  echo "SKIP_GUIDANCE_LOAD=true: not loading guidance."
  exit 0
fi

uv run govuk-rag-fetch

# New role assignments can take a few minutes to apply, so retry the Azure steps.
attempt=1
until uv run govuk-rag-upload && uv run govuk-rag-ingest; do
  if [ "$attempt" -ge 6 ]; then
    echo "Loading guidance failed after $attempt attempts." >&2
    exit 1
  fi
  echo "Attempt $attempt failed (role assignments may still be applying). Retrying in 30s..."
  attempt=$((attempt + 1))
  sleep 30
done
