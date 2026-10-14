// Assigns V3_Audit_Fields permset to every active User in the org so
// integration users writing through the SF Auth Proxy JWT-bearer flow
// can set Agent_Id__c/Session_Id__c/Correlation_Id__c/Research_Brief_Id__c
// and the other 7 v3 audit fields.
//
// Idempotent: skips users who already have the assignment.
// Zero credentials. Safe to rerun.

PermissionSet ps = [
    SELECT Id FROM PermissionSet WHERE Name = 'V3_Audit_Fields' LIMIT 1
];
Set<Id> already = new Set<Id>();
for (PermissionSetAssignment a : [
    SELECT AssigneeId FROM PermissionSetAssignment
    WHERE PermissionSetId = :ps.Id
]) {
    already.add(a.AssigneeId);
}
List<PermissionSetAssignment> adds = new List<PermissionSetAssignment>();
for (User u : [
    SELECT Id, Profile.UserLicense.Name FROM User
    WHERE IsActive = TRUE AND UserType = 'Standard'
      AND Profile.UserLicense.Name = 'Salesforce'
]) {
    if (!already.contains(u.Id)) {
        adds.add(new PermissionSetAssignment(
            AssigneeId = u.Id,
            PermissionSetId = ps.Id
        ));
    }
}
if (!adds.isEmpty()) {
    insert adds;
    System.debug('assigned V3_Audit_Fields to ' + adds.size() + ' users');
} else {
    System.debug('no new assignments needed');
}
