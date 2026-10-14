// Assign WA permission sets to the current user
// Run: sf apex run --file scripts/apex/assign-permission-sets.apex
//
// This assigns all 3 WA permission sets (Advisor, Compliance Officer, Admin)
// to the currently logged-in user. In production, assign selectively based on role.

Id currentUserId = UserInfo.getUserId();
String currentUserName = UserInfo.getName();

List<String> permSetNames = new List<String>{
    'WA_Advisor',
    'WA_Compliance_Officer',
    'WA_Admin'
};

// Get permission set IDs
List<PermissionSet> permSets = [
    SELECT Id, Name FROM PermissionSet
    WHERE Name IN :permSetNames
];

// Check which are already assigned
Set<Id> alreadyAssigned = new Set<Id>();
for (PermissionSetAssignment psa : [
    SELECT PermissionSetId FROM PermissionSetAssignment
    WHERE AssigneeId = :currentUserId AND PermissionSetId IN :permSets
]) {
    alreadyAssigned.add(psa.PermissionSetId);
}

// Assign missing ones
List<PermissionSetAssignment> toInsert = new List<PermissionSetAssignment>();
for (PermissionSet ps : permSets) {
    if (!alreadyAssigned.contains(ps.Id)) {
        toInsert.add(new PermissionSetAssignment(
            AssigneeId = currentUserId,
            PermissionSetId = ps.Id
        ));
        System.debug('Assigning: ' + ps.Name + ' → ' + currentUserName);
    } else {
        System.debug('Already assigned: ' + ps.Name);
    }
}

if (!toInsert.isEmpty()) {
    insert toInsert;
    System.debug('Assigned ' + toInsert.size() + ' permission sets to ' + currentUserName);
} else {
    System.debug('All permission sets already assigned to ' + currentUserName);
}
