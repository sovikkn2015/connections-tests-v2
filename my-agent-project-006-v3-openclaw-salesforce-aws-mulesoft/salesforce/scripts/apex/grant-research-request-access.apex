// Grant ReadWrite on Research_Request__c to all Salesforce-licensed users
// by adding it to the existing V3_Audit_Fields permset (mirrors how we
// granted Client_Inquiry__c access). Idempotent.
//
// WARNING: this script uses Metadata API via Apex which requires
// "Modify All Data" + "Modify Metadata" permissions. For speed we use
// PermissionSetAssignment directly instead of FLS tweaks — the permset
// already grants object-level RW.

// Create a dedicated permset for Research_Request__c if it doesn't exist.
List<PermissionSet> existing = [
    SELECT Id, Name FROM PermissionSet
    WHERE Name = 'V3_Research_Request_Access' LIMIT 1
];
if (existing.isEmpty()) {
    System.debug('V3_Research_Request_Access permset does not exist — create via metadata deploy, then re-run');
} else {
    Id psId = existing[0].Id;
    Set<Id> alreadyAssigned = new Set<Id>();
    for (PermissionSetAssignment a : [
        SELECT AssigneeId FROM PermissionSetAssignment
        WHERE PermissionSetId = :psId
    ]) {
        alreadyAssigned.add(a.AssigneeId);
    }
    List<PermissionSetAssignment> adds = new List<PermissionSetAssignment>();
    for (User u : [
        SELECT Id FROM User
        WHERE IsActive = TRUE
          AND UserType = 'Standard'
          AND Profile.UserLicense.Name = 'Salesforce'
    ]) {
        if (!alreadyAssigned.contains(u.Id)) {
            adds.add(new PermissionSetAssignment(
                AssigneeId = u.Id,
                PermissionSetId = psId
            ));
        }
    }
    if (!adds.isEmpty()) {
        insert adds;
        System.debug('Assigned V3_Research_Request_Access to ' + adds.size() + ' users');
    } else {
        System.debug('No new assignments needed');
    }
}
