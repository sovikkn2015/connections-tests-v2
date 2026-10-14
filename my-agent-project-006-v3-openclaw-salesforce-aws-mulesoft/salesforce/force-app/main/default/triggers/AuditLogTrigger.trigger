// V3 trigger — immutability + raw-token guard on IR_Audit_Log__c.
// Steering rule 22: never persist raw approval tokens; only hashes.
// Steering rule 10: every attempt writes an audit row, but after insert
// those rows are immutable.
trigger AuditLogTrigger on IR_Audit_Log__c (before insert, before update, before delete) {
    if (Trigger.isInsert) {
        for (IR_Audit_Log__c row : Trigger.new) {
            String gate = row.Gate_Trace__c != null ? row.Gate_Trace__c : '';
            if (gate.containsIgnoreCase('approval_token=') && !gate.containsIgnoreCase('approval_token_hash=')) {
                row.addError('Gate_Trace__c may not contain raw approval_token — hash only (steering rule 22).');
            }
            if (row.Timestamp__c == null) {
                row.Timestamp__c = Datetime.now();
            }
        }
    } else if (Trigger.isUpdate || Trigger.isDelete) {
        Set<Id> allowedIds = new Set<Id>();
        for (PermissionSetAssignment psa : [
            SELECT AssigneeId FROM PermissionSetAssignment
             WHERE AssigneeId = :UserInfo.getUserId()
               AND PermissionSet.Name = 'Senior_Compliance_Approver'
        ]) {
            allowedIds.add(psa.AssigneeId);
        }
        if (!allowedIds.contains(UserInfo.getUserId())) {
            for (IR_Audit_Log__c row : (Trigger.isDelete ? Trigger.old : Trigger.new)) {
                row.addError('IR_Audit_Log__c records are immutable after insert.');
            }
        }
    }
}
