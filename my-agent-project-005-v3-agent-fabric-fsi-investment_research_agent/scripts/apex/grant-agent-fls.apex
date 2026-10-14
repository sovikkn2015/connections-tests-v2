// Grant object + field permissions to Einstein Agent User
// This is required for the agent to read CRM data via Apex actions
// Run: sf apex run --file scripts/apex/grant-agent-fls.apex
//
// NOTE: Uses hardcoded field list because anonymous Apex has a stale
// schema cache on fresh orgs. Ticker__c is excluded because it is
// required + unique + externalId, making it non-permissionable.

Id psId = [SELECT Id FROM PermissionSet WHERE IsOwnedByProfile = true AND Profile.Name = 'Einstein Agent User' LIMIT 1].Id;

// --- Object permissions ---
List<String> objectNames = new List<String>{
    'IR_Company__c', 'IR_Coverage__c', 'IR_Watchlist__c', 'IR_Research_Note__c', 'IR_Audit_Log__c'
};

Set<String> existingObjects = new Set<String>();
for (ObjectPermissions op : [SELECT SobjectType FROM ObjectPermissions WHERE ParentId = :psId AND SobjectType IN :objectNames]) {
    existingObjects.add(op.SobjectType);
}

List<ObjectPermissions> objPerms = new List<ObjectPermissions>();
for (String objName : objectNames) {
    if (!existingObjects.contains(objName)) {
        objPerms.add(new ObjectPermissions(
            ParentId = psId,
            SobjectType = objName,
            PermissionsRead = true,
            PermissionsCreate = true,
            PermissionsEdit = true
        ));
    }
}
if (!objPerms.isEmpty()) {
    insert objPerms;
    System.debug('Granted object access for ' + objPerms.size() + ' objects');
} else {
    System.debug('All objects already have access for Einstein Agent User');
}

// --- Field permissions ---
// Excludes IR_Company__c.Ticker__c (required+unique+externalId = non-permissionable)
List<String> fieldNames = new List<String>{
    // IR_Company__c (5 permissionable fields — Ticker__c excluded)
    'IR_Company__c.Sector__c', 'IR_Company__c.Exchange__c',
    'IR_Company__c.Market_Cap__c', 'IR_Company__c.Last_Price__c', 'IR_Company__c.Earnings_Date__c',
    // IR_Coverage__c (5 fields)
    'IR_Coverage__c.Company__c', 'IR_Coverage__c.Analyst__c', 'IR_Coverage__c.Rating__c',
    'IR_Coverage__c.Target_Price__c', 'IR_Coverage__c.Last_Updated__c',
    // IR_Watchlist__c (5 fields)
    'IR_Watchlist__c.Company__c', 'IR_Watchlist__c.Analyst__c', 'IR_Watchlist__c.Priority__c',
    'IR_Watchlist__c.Reason__c', 'IR_Watchlist__c.Added_Date__c',
    // IR_Research_Note__c (10 fields)
    'IR_Research_Note__c.Company__c', 'IR_Research_Note__c.Ticker__c', 'IR_Research_Note__c.Analyst__c',
    'IR_Research_Note__c.Rating__c', 'IR_Research_Note__c.Target_Price__c', 'IR_Research_Note__c.Summary__c',
    'IR_Research_Note__c.Full_Brief__c', 'IR_Research_Note__c.Generated_Date__c',
    'IR_Research_Note__c.Data_Sources__c', 'IR_Research_Note__c.Status__c',
    // IR_Audit_Log__c (9 fields)
    'IR_Audit_Log__c.Agent__c', 'IR_Audit_Log__c.Action__c', 'IR_Audit_Log__c.Query__c',
    'IR_Audit_Log__c.Analyst__c', 'IR_Audit_Log__c.Timestamp__c', 'IR_Audit_Log__c.Data_Sources_Used__c',
    'IR_Audit_Log__c.Trace_Id__c', 'IR_Audit_Log__c.Platform__c', 'IR_Audit_Log__c.Duration_Ms__c'
};

Set<String> existingFields = new Set<String>();
for (FieldPermissions fp : [SELECT Field FROM FieldPermissions WHERE ParentId = :psId AND Field IN :fieldNames]) {
    existingFields.add(fp.Field);
}

List<FieldPermissions> fieldPerms = new List<FieldPermissions>();
for (String fn : fieldNames) {
    if (!existingFields.contains(fn)) {
        fieldPerms.add(new FieldPermissions(
            ParentId = psId,
            SobjectType = fn.substringBefore('.'),
            Field = fn,
            PermissionsRead = true,
            PermissionsEdit = true
        ));
    }
}
if (!fieldPerms.isEmpty()) {
    insert fieldPerms;
    System.debug('Granted FLS for ' + fieldPerms.size() + ' fields to Einstein Agent User');
} else {
    System.debug('All fields already have FLS for Einstein Agent User');
}
