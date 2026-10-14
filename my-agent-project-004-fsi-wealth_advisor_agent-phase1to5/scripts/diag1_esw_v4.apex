// Check for Messaging for In-App and Web deployments
List<MessagingDeployment> deps = [SELECT Id, DeveloperName, MasterLabel FROM MessagingDeployment];
for (MessagingDeployment d : deps) {
    System.debug('MessagingDeployment: ' + d.MasterLabel + ' | Dev: ' + d.DeveloperName);
}
System.debug('Total MessagingDeployment records: ' + deps.size());
