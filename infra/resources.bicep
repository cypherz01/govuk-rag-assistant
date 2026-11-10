// Everything the assistant runs on. No keys anywhere: local auth is disabled on Storage, Search
// and OpenAI, and the app reaches them with a user-assigned managed identity.

param location string
param searchLocation string
param tags object
param resourceToken string
param principalId string
param principalType string
param apiExists bool
@secure()
param demoKey string
param searchSku string
param chatModelName string
param chatModelVersion string
param chatCapacity int
param embeddingCapacity int

var containerName = 'govuk-guidance'
var chatDeploymentName = 'chat'
var embeddingDeploymentName = 'text-embedding-3-small'
var placeholderImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// Built-in role definition ids.
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}

// ---------------------------------------------------------------------------------------------
// Identity, logs and registry
// ---------------------------------------------------------------------------------------------

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-api-${resourceToken}'
  location: location
  tags: tags
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'cr${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
  }
}

resource appAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, roles.acrPull)
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
  }
}

// ---------------------------------------------------------------------------------------------
// Blob Storage: the source documents
// ---------------------------------------------------------------------------------------------

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${resourceToken}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }

  resource blobService 'blobServices' = {
    name: 'default'

    resource container 'containers' = {
      name: containerName
    }
  }
}

resource userBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(storage.id, principalId, roles.storageBlobDataContributor)
  scope: storage
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
  }
}

// ---------------------------------------------------------------------------------------------
// Azure AI Search: the chunk index
// ---------------------------------------------------------------------------------------------

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: 'srch-${resourceToken}'
  location: searchLocation
  tags: tags
  sku: { name: searchSku }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    disableLocalAuth: true
    publicNetworkAccess: 'enabled'
  }
}

resource appSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, identity.id, roles.searchIndexDataReader)
  scope: search
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataReader)
  }
}

resource userSearchDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(search.id, principalId, roles.searchIndexDataContributor)
  scope: search
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
  }
}

resource userSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(search.id, principalId, roles.searchServiceContributor)
  scope: search
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
  }
}

// ---------------------------------------------------------------------------------------------
// Azure OpenAI: embeddings and chat, pay per token
// ---------------------------------------------------------------------------------------------

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'oai-${resourceToken}'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: 'oai-${resourceToken}' // required for Entra ID auth
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: chatDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: embeddingDeploymentName
  dependsOn: [chatDeployment] // deployments on one account must be created one at a time
  sku: {
    name: 'GlobalStandard' // regional 'Standard' is not offered for this model in uksouth
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
}

resource appOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, identity.id, roles.openAiUser)
  scope: openAi
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
  }
}

resource userOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(openAi.id, principalId, roles.openAiUser)
  scope: openAi
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
  }
}

// ---------------------------------------------------------------------------------------------
// Container Apps: the FastAPI service, scaling to zero when idle
// ---------------------------------------------------------------------------------------------

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var appName = 'ca-api-${resourceToken}'

module existingImage 'modules/existing-image.bicep' = {
  name: 'existing-api-image'
  params: {
    exists: apiExists
    name: appName
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  dependsOn: [appAcrPull]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: [
        {
          name: 'demo-key'
          value: demoKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: empty(existingImage.outputs.image) ? placeholderImage : existingImage.outputs.image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'RAG_AZURE_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net/' }
            { name: 'RAG_AZURE_OPENAI_ENDPOINT', value: openAi.properties.endpoint }
            { name: 'RAG_SEARCH_INDEX_NAME', value: containerName }
            { name: 'RAG_CHAT_DEPLOYMENT', value: chatDeployment.name }
            { name: 'RAG_EMBEDDING_DEPLOYMENT', value: embeddingDeployment.name }
            { name: 'RAG_DEMO_KEY', secretRef: 'demo-key' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health', port: 8000 }
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

output registryLoginServer string = registry.properties.loginServer
output appName string = app.name
output appUri string = 'https://${app.properties.configuration.ingress.fqdn}'
output storageAccountUrl string = storage.properties.primaryEndpoints.blob
output searchEndpoint string = 'https://${search.name}.search.windows.net/'
output openAiEndpoint string = openAi.properties.endpoint
output chatDeployment string = chatDeployment.name
output embeddingDeployment string = embeddingDeployment.name
