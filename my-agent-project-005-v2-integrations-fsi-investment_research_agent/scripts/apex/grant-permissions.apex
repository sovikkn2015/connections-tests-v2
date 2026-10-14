// Grant Apex class access to Einstein Agent User profile — All Sprints
// Run: sf apex run --file scripts/apex/grant-permissions.apex

Id psId = [SELECT Id FROM PermissionSet WHERE IsOwnedByProfile = true AND Profile.Name = 'Einstein Agent User' LIMIT 1].Id;

List<ApexClass> classes = [SELECT Id, Name FROM ApexClass WHERE Name IN (
    'IR_CompanyLookupAction',
    'IR_CoverageCheckAction',
    'IR_EarningsCalendarAction',
    'IR_WatchlistAction',
    'IR_ComplianceScreeningAction',
    'IR_AuditLogAction',
    'IR_SecFilingsAction',
    'IR_MarketDataAction',
    'IR_NewsSearchAction',
    'IR_FinancialAnalysisAction',
    'IR_SentimentAnalysisAction',
    'IR_SeedDataRunner',
    'IR_LangfuseTracer'
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
