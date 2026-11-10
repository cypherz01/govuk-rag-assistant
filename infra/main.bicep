// Entry point for `azd provision`: creates the resource group and everything in it.
targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd environment name; used to name the resource group and resources.')
param environmentName string

@minLength(1)
@description('Region for all resources.')
param location string

@description('Region for Azure AI Search, if different from location (free-tier capacity varies).')
param searchLocation string = ''

@description('Object id of the person running azd. Gets the roles needed to load and index guidance.')
param principalId string = ''

@allowed(['User', 'ServicePrincipal'])
@description('Type of principalId: User locally, ServicePrincipal in CI.')
param principalType string = 'User'

@description('Set by azd once the app has been deployed, so re-provisioning keeps its image.')
param apiExists bool = false

@secure()
@description('Shared demo key for /chat. azd generates one and stores it in the environment.')
@metadata({
  azd: {
    type: 'generate'
    config: { length: 32, noSpecial: true }
  }
})
param demoKey string

@allowed(['free', 'basic'])
@description('Azure AI Search tier. Only one free search service is allowed per subscription.')
param searchSku string = 'free'

@description('Chat model and version to deploy (deployment name is always "chat").')
param chatModelName string = 'gpt-4.1-mini'
param chatModelVersion string = '2025-04-14'

@description('Chat model capacity, in thousands of tokens per minute.')
param chatCapacity int = 30

@description('Embedding model capacity, in thousands of tokens per minute.')
param embeddingCapacity int = 30

var tags = { 'azd-env-name': environmentName }

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    searchLocation: empty(searchLocation) ? location : searchLocation
    tags: tags
    resourceToken: toLower(uniqueString(subscription().id, environmentName, location))
    principalId: principalId
    principalType: principalType
    apiExists: apiExists
    demoKey: demoKey
    searchSku: searchSku
    chatModelName: chatModelName
    chatModelVersion: chatModelVersion
    chatCapacity: chatCapacity
    embeddingCapacity: embeddingCapacity
  }
}

// azd reads these. The RAG_* values also reach the postprovision hook, and
// `azd env get-values` gives them to a local .env for running ingestion or the app.
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryLoginServer
output SERVICE_API_NAME string = resources.outputs.appName
output SERVICE_API_URI string = resources.outputs.appUri
output RAG_AZURE_STORAGE_ACCOUNT_URL string = resources.outputs.storageAccountUrl
output RAG_AZURE_SEARCH_ENDPOINT string = resources.outputs.searchEndpoint
output RAG_AZURE_OPENAI_ENDPOINT string = resources.outputs.openAiEndpoint
output RAG_CHAT_DEPLOYMENT string = resources.outputs.chatDeployment
output RAG_EMBEDDING_DEPLOYMENT string = resources.outputs.embeddingDeployment
