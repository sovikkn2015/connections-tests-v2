List<ServicePresenceStatus> statuses = [SELECT Id, MasterLabel, DeveloperName FROM ServicePresenceStatus];
for (ServicePresenceStatus s : statuses) {
    System.debug('Presence: ' + s.MasterLabel + ' | Dev: ' + s.DeveloperName);
}
System.debug('Total ServicePresenceStatus records: ' + statuses.size());
