// Try EmbeddedServiceDeployment instead
List<SObject> deployments = [SELECT Id, DeveloperName, MasterLabel FROM EmbeddedServiceDeployment];
for (SObject d : deployments) {
    System.debug('ESW Deployment: ' + d.get('MasterLabel') + ' | Dev: ' + d.get('DeveloperName'));
}
System.debug('Total EmbeddedServiceDeployment records: ' + deployments.size());
