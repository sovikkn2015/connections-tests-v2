// Grant Field-Level Security for all IR custom fields to System Administrator profile
// Run once after first deploy: sf apex run --file scripts/apex/grant-fls.apex

List<String> fieldNames = new List<String>{
    // IR_Company__c fields (Ticker__c excluded — required+unique+externalId = non-permissionable)
    'IR_Company__c.Sector__c', 'IR_Company__c.Exchange__c',
    'IR_Company__c.Market_Cap__c', 'IR_Company__c.Last_Price__c', 'IR_Company__c.Earnings_Date__c',
    // IR_Coverage__c fields
    'IR_Coverage__c.Company__c', 'IR_Coverage__c.Analyst__c', 'IR_Coverage__c.Rating__c',
    'IR_Coverage__c.Target_Price__c', 'IR_Coverage__c.Last_Updated__c',
    // IR_Watchlist__c fields
    'IR_Watchlist__c.Company__c', 'IR_Watchlist__c.Analyst__c', 'IR_Watchlist__c.Priority__c',
    'IR_Watchlist__c.Reason__c', 'IR_Watchlist__c.Added_Date__c',
    // IR_Research_Note__c fields
    'IR_Research_Note__c.Company__c', 'IR_Research_Note__c.Ticker__c', 'IR_Research_Note__c.Analyst__c',
    'IR_Research_Note__c.Rating__c', 'IR_Research_Note__c.Target_Price__c', 'IR_Research_Note__c.Summary__c',
    'IR_Research_Note__c.Full_Brief__c', 'IR_Research_Note__c.Generated_Date__c',
    'IR_Research_Note__c.Data_Sources__c', 'IR_Research_Note__c.Status__c',
    // IR_Audit_Log__c fields
    'IR_Audit_Log__c.Agent__c', 'IR_Audit_Log__c.Action__c', 'IR_Audit_Log__c.Query__c',
    'IR_Audit_Log__c.Analyst__c', 'IR_Audit_Log__c.Timestamp__c', 'IR_Audit_Log__c.Data_Sources_Used__c',
    'IR_Audit_Log__c.Trace_Id__c', 'IR_Audit_Log__c.Platform__c', 'IR_Audit_Log__c.Duration_Ms__c'
};

Id psId = [SELECT Id FROM PermissionSet WHERE IsOwnedByProfile = true AND Profile.Name = 'System Administrator' LIMIT 1].Id;

// Check which permissions already exist
Set<String> existing = new Set<String>();
for (FieldPermissions fp : [SELECT Field FROM FieldPermissions WHERE ParentId = :psId AND Field IN :fieldNames]) {
    existing.add(fp.Field);
}

List<FieldPermissions> perms = new List<FieldPermissions>();
for (String fn : fieldNames) {
    if (!existing.contains(fn)) {
        perms.add(new FieldPermissions(
            ParentId = psId,
            SobjectType = fn.substringBefore('.'),
            Field = fn,
            PermissionsRead = true,
            PermissionsEdit = true
        ));
    }
}

if (!perms.isEmpty()) {
    insert perms;
    System.debug('Granted FLS for ' + perms.size() + ' fields');
} else {
    System.debug('All fields already have FLS granted');
}
