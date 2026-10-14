// Fix: remove Number field, use VersionNumber or just query available fields
List<BotVersion> versions = [SELECT Id, DeveloperName, Status FROM BotVersion WHERE BotDefinition.DeveloperName = 'WA_P1to5_Advisor' ORDER BY CreatedDate DESC LIMIT 5];
for (BotVersion v : versions) {
    System.debug('BotVersion: ' + v.DeveloperName + ' | Status: ' + v.Status);
}
System.debug('Total BotVersion records: ' + versions.size());
