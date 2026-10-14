// Grant Field-Level Security for all WA custom fields to System Administrator profile
// Run once after first deploy: sf apex run --file scripts/apex/grant-fls.apex

List<String> fieldNames = new List<String>{
    // Household fields
    'WA_Household__c.Total_AUM__c', 'WA_Household__c.Risk_Profile__c', 'WA_Household__c.Advisor__c',
    // Client fields
    'WA_Client__c.Household__c', 'WA_Client__c.Email__c', 'WA_Client__c.Phone__c', 'WA_Client__c.Role__c',
    // Financial Account fields
    'WA_Financial_Account__c.Client__c', 'WA_Financial_Account__c.Type__c', 'WA_Financial_Account__c.Balance__c',
    'WA_Financial_Account__c.Allocation__c', 'WA_Financial_Account__c.YTD_Return__c', 'WA_Financial_Account__c.Target_Allocation__c',
    // Financial Goal fields
    'WA_Financial_Goal__c.Client__c', 'WA_Financial_Goal__c.Target_Amount__c', 'WA_Financial_Goal__c.Current_Amount__c', 'WA_Financial_Goal__c.Target_Date__c',
    // Meeting fields
    'WA_Meeting__c.Client__c', 'WA_Meeting__c.Date_Time__c', 'WA_Meeting__c.Location__c', 'WA_Meeting__c.Notes__c', 'WA_Meeting__c.Action_Items__c',
    // Transaction fields (NEW)
    'WA_Transaction__c.Client__c', 'WA_Transaction__c.Account__c', 'WA_Transaction__c.Type__c', 'WA_Transaction__c.Amount__c',
    'WA_Transaction__c.Date__c', 'WA_Transaction__c.Description__c', 'WA_Transaction__c.Symbol__c',
    // Referral fields (NEW)
    'WA_Referral__c.Client__c', 'WA_Referral__c.Source__c', 'WA_Referral__c.Source_Type__c',
    'WA_Referral__c.Date__c', 'WA_Referral__c.Status__c', 'WA_Referral__c.Value__c',
    // Audit Log fields (NEW — Phase 5)
    'WA_Audit_Log__c.Agent_Name__c', 'WA_Audit_Log__c.User__c', 'WA_Audit_Log__c.Topic__c',
    'WA_Audit_Log__c.Action__c', 'WA_Audit_Log__c.Query__c', 'WA_Audit_Log__c.Response_Summary__c',
    'WA_Audit_Log__c.Client_Accessed__c', 'WA_Audit_Log__c.Timestamp__c', 'WA_Audit_Log__c.Session_Id__c'
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
