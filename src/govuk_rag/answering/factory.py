"""Wiring the answerer to Azure AI Search and Azure OpenAI.

Authenticates with ``DefaultAzureCredential`` (``az login`` locally, managed identity in Azure),
so no keys are configured. Building the clients makes no network calls.
"""

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from govuk_rag.answering.answerer import Answerer
from govuk_rag.answering.chat_model import AzureOpenAIChatModel
from govuk_rag.answering.retrieval import AzureSearchRetriever
from govuk_rag.config import Settings
from govuk_rag.ingestion.embeddings import AzureOpenAIEmbedder

_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


def build_answerer(settings: Settings) -> Answerer | None:
    """The production answerer, or ``None`` if the Search or OpenAI endpoint is not configured."""
    search_url = settings.azure_search_endpoint
    openai_url = settings.azure_openai_endpoint
    if search_url is None or openai_url is None:
        return None

    credential = DefaultAzureCredential()
    openai_client = AzureOpenAI(
        azure_endpoint=str(openai_url),
        api_version=settings.azure_openai_api_version,
        azure_ad_token_provider=get_bearer_token_provider(credential, _COGNITIVE_SERVICES_SCOPE),
    )
    retriever = AzureSearchRetriever(
        SearchClient(str(search_url), settings.search_index_name, credential),
        AzureOpenAIEmbedder(openai_client, deployment=settings.embedding_deployment),
        top=settings.retrieval_top_k,
    )
    chat_model = AzureOpenAIChatModel(
        openai_client,
        deployment=settings.chat_deployment,
        max_output_tokens=settings.max_output_tokens,
    )
    return Answerer(retriever, chat_model, relevance_threshold=settings.relevance_threshold)
