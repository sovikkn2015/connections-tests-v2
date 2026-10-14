List<MessagingChannel> channels = [SELECT Id, DeveloperName, MasterLabel, IsActive FROM MessagingChannel];
for (MessagingChannel ch : channels) {
    System.debug('Channel: ' + ch.MasterLabel + ' | Active: ' + ch.IsActive + ' | Dev: ' + ch.DeveloperName);
}
System.debug('Total MessagingChannel records: ' + channels.size());
