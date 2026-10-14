// Check for Embedded Service via metadata - try LiveChatDeployment and LiveChatButton
List<LiveChatDeployment> lcDeps = [SELECT Id, DeveloperName, MasterLabel FROM LiveChatDeployment];
for (LiveChatDeployment d : lcDeps) {
    System.debug('LiveChatDeployment: ' + d.MasterLabel + ' | Dev: ' + d.DeveloperName);
}
System.debug('Total LiveChatDeployment records: ' + lcDeps.size());

List<LiveChatButton> lcButtons = [SELECT Id, DeveloperName, MasterLabel, IsActive FROM LiveChatButton];
for (LiveChatButton b : lcButtons) {
    System.debug('LiveChatButton: ' + b.MasterLabel + ' | Dev: ' + b.DeveloperName + ' | Active: ' + b.IsActive);
}
System.debug('Total LiveChatButton records: ' + lcButtons.size());
