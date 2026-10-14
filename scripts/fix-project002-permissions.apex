// Grant Apex class access to Einstein Agent User for Project 002 SOQL classes
// This fixes the WA_Advisor_v2 agent not calling actions

Id psId = [SELECT Id FROM PermissionSet WHERE IsOwnedByProfile = true AND Profile.Name = 'Einstein Agent User' LIMIT 1].Id;

List<ApexClass> classes = [SELECT Id, Name FROM ApexClass WHERE Name IN (
    'ClientLookupAction', 'PortfolioReviewAction', 'GoalPlanningAction', 'MeetingPrepAction', 'HelloAction'
)];

Set<Id> existingIds = new Set<Id>();
for (SetupEntityAccess a : [SELECT SetupEntityId FROM SetupEntityAccess WHERE ParentId = :psId AND SetupEntityType = 'ApexClass']) {
    existingIds.add(a.SetupEntityId);
}

List<SetupEntityAccess> toInsert = new List<SetupEntityAccess>();
for (ApexClass c : classes) {
    if (!existingIds.contains(c.Id)) {
        toInsert.add(new SetupEntityAccess(ParentId = psId, SetupEntityId = c.Id));
        System.debug('Granting: ' + c.Name);
    }
}

if (!toInsert.isEmpty()) {
    insert toInsert;
    System.debug('Granted ' + toInsert.size() + ' classes to Einstein Agent User');
} else {
    System.debug('All classes already accessible');
}
