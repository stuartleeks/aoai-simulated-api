targetScope = 'resourceGroup'

@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

@description('The mode the simulator should run in')
param simulatorMode string

@description('The API key the simulator will use to authenticate requests')
@secure()
param simulatorApiKey string

var containerRegistryName = replace('aoaisim-${baseName}', '-', '')
var containerAppEnvName = 'aoaisim-${baseName}'
var logAnalyticsName = 'aoaisim-${baseName}'
var keyVaultName = replace('aoaisim-${baseName}', '-', '')

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-12-01-preview' existing = {
  name: containerRegistryName
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}
var keyVaultUri = vault.properties.vaultUri

resource acrPullRoleDefinition 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: subscription()
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d' // https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#acrpull
}
resource assignAcrPullToAca 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, containerRegistry.name, managedIdentity.name, 'AssignAcrPullToAks')
  scope: containerRegistry
  properties: {
    description: 'Assign AcrPull role to ACA identity'
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinition.id
  }
}
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${containerAppEnvName}-identity'
  location: location
}

resource keyVaultSecretsUserRoleDefinition 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: subscription()
  name: '4633458b-17de-408a-b874-0445c86b69e6' // https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide?tabs=azure-cli
}
resource assignSecretsReaderRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, vault.name, managedIdentity.name, 'assignSecretsReaderRole')
  scope: vault
  properties: {
    description: 'Assign Key Vault Secrets Reader role to ACA identity'
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinition.id
  }
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2022-03-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}



// TODO - OPEN AI key etc go here
resource simulatorApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' =  {
  parent: vault
  name: 'simulator-api-key'
  properties: {
    value: simulatorApiKey
  }
}



resource apiSim 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'aoai-simulated-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {} // use this for accessing ACR, secrets
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'single'
      // setting maxInactiveRevisions to 0 makes it easier when iterating and fixing issues by preventing 
      // old revisions showing in logs etc
      maxInactiveRevisions: 0
      ingress: {
        external: true
        targetPort: 8000
      }
      secrets: [
        {
          name: 'simulator-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/simulator-api-key'
          identity: managedIdentity.id
        }
      ]
      registries: [
        {
          identity: managedIdentity.id
          server: containerRegistry.properties.loginServer
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'aoai-simulated-api'
          image: '${containerRegistry.properties.loginServer}/aoai-simulated-api:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'SIMULATOR_API_KEY'
              secretRef: 'simulator-api-key'
            }
            {
              name: 'SIMULATOR_MODE'
              value: simulatorMode
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}



output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerRegistryName string = containerRegistry.name
output apiSimFqdn string = apiSim.properties.configuration.ingress.fqdn
