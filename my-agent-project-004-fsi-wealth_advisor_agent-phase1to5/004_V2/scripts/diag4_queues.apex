List<Group> queues = [SELECT Id, Name, DeveloperName, Type FROM Group WHERE Type = 'Queue'];
for (Group g : queues) {
    System.debug('Queue: ' + g.Name + ' | Dev: ' + g.DeveloperName);
}
System.debug('Total Queue records: ' + queues.size());
