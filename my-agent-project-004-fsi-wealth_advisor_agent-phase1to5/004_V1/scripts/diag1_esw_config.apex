List<EmbeddedServiceConfig> configs = [SELECT Id, DeveloperName, MasterLabel, IsEnabled__c, Site FROM EmbeddedServiceConfig];
for (EmbeddedServiceConfig c : configs) {
    System.debug('ESW Config: ' + c.MasterLabel + ' | Enabled: ' + c.IsEnabled__c + ' | Site: ' + c.Site);
}
System.debug('Total EmbeddedServiceConfig records: ' + configs.size());
