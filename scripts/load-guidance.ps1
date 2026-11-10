# Fetch the GOV.UK guidance, upload it to Blob Storage and index it in Azure AI Search.
# Run by azd after provisioning; azd supplies the RAG_* endpoints from the Bicep outputs.
# Re-runnable: unchanged documents are not re-uploaded into the index or re-embedded.
$ErrorActionPreference = 'Stop'

if ($env:SKIP_GUIDANCE_LOAD -eq 'true') {
    Write-Host 'SKIP_GUIDANCE_LOAD=true: not loading guidance.'
    exit 0
}

uv run govuk-rag-fetch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# New role assignments can take a few minutes to apply, so retry the Azure steps.
$maxAttempts = 6
for ($attempt = 1; ; $attempt++) {
    uv run govuk-rag-upload
    if ($LASTEXITCODE -eq 0) {
        uv run govuk-rag-ingest
        if ($LASTEXITCODE -eq 0) { break }
    }
    if ($attempt -ge $maxAttempts) {
        Write-Error "Loading guidance failed after $attempt attempts."
        exit 1
    }
    Write-Host "Attempt $attempt failed (role assignments may still be applying). Retrying in 30s..."
    Start-Sleep -Seconds 30
}
