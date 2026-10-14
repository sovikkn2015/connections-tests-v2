// Grant permissions for Data Cloud agent — Phase 1-5
// Run: sf apex run --file scripts/apex/grant-permissions.apex

// 1. Grant Apex class access to Einstein Agent User profile
Id psId = [SELECT Id FROM PermissionSet WHERE IsOwnedByProfile = true AND Profile.Name = 'Einstein Agent User' LIMIT 1].Id;

List<ApexClass> classes = [SELECT Id, Name FROM ApexClass WHERE Name IN (
    'DC_ClientLookupAction',
    'DC_PortfolioReviewAction',
    'DC_GoalPlanningAction',
    'DC_MeetingPrepAction',
    'DC_RebalancingAction',
    'DC_TransactionHistoryAction',
    'DC_ComplianceCheckAction',
    'DC_ReferralTrackingAction',
    'DC_AuditLogAction',
    'DC_MarketDataAction',
    'DC_NewsSearchAction'
)];

Set<Id> existingIds = new Set<Id>();
for (SetupEntityAccess a : [SELECT SetupEntityId FROM SetupEntityAccess WHERE ParentId = :psId AND SetupEntityType = 'ApexClass']) {
    existingIds.add(a.SetupEntityId);
}

List<SetupEntityAccess> toInsert = new List<SetupEntityAccess>();
for (ApexClass c : classes) {
    if (!existingIds.contains(c.Id)) {
        toInsert.add(new SetupEntityAccess(ParentId = psId, SetupEntityId = c.Id));
        System.debug('Granting Apex access: ' + c.Name);
    }
}

if (!toInsert.isEmpty()) {
    insert toInsert;
    System.debug('Granted Apex class access for ' + toInsert.size() + ' classes');
} else {
    System.debug('All classes already accessible');
}
