List<BotVersion> versions = [SELECT Id, DeveloperName, Number, Status FROM BotVersion WHERE BotDefinition.DeveloperName = 'WA_P1to5_Advisor' ORDER BY Number DESC LIMIT 5];
for (BotVersion v : versions) {
    System.debug('Version: ' + v.Number + ' | Status: ' + v.Status + ' | Dev: ' + v.DeveloperName);
}
System.debug('Total BotVersion records: ' + versions.size());
