// The image the container app is currently running, so re-provisioning doesn't replace the
// deployed app with the placeholder. A separate module because a template can't read a
// resource it is also redefining.
param exists bool
param name string

resource existingApp 'Microsoft.App/containerApps@2024-03-01' existing = if (exists) {
  name: name
}

#disable-next-line BCP318 // only read when the app exists
output image string = exists ? existingApp.properties.template.containers[0].image : ''
