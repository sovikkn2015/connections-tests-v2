List<BotDefinition> bots = [SELECT Id, DeveloperName, MasterLabel, Description FROM BotDefinition WHERE DeveloperName LIKE '%WA%'];
for (BotDefinition b : bots) {
    System.debug('Bot: ' + b.MasterLabel + ' | Dev: ' + b.DeveloperName + ' | Desc: ' + b.Description);
}
System.debug('Total matching BotDefinition records: ' + bots.size());
