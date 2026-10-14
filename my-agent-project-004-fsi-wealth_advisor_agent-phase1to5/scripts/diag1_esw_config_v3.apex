// Try multiple possible object names for Embedded Service
// Approach 1: Try ServiceChannel
List<ServiceChannel> channels = [SELECT Id, DeveloperName, MasterLabel, RelatedEntity FROM ServiceChannel];
for (ServiceChannel sc : channels) {
    System.debug('ServiceChannel: ' + sc.MasterLabel + ' | Dev: ' + sc.DeveloperName + ' | Entity: ' + sc.RelatedEntity);
}
System.debug('Total ServiceChannel records: ' + channels.size());
