@isTest
private class AuditLogTriggerTest {
    @isTest static void insert_sets_timestamp() {
        IR_Audit_Log__c row = new IR_Audit_Log__c(
            Principal_Id__c = 'sarah@firm.com',
            Action__c = 'RESEARCH_PUBLISHED'
        );
        insert row;
        IR_Audit_Log__c loaded = [SELECT Timestamp__c FROM IR_Audit_Log__c WHERE Id = :row.Id];
        System.assertNotEquals(null, loaded.Timestamp__c);
    }

    @isTest static void rejects_raw_approval_token_in_gate_trace() {
        IR_Audit_Log__c row = new IR_Audit_Log__c(
            Principal_Id__c = 'rm@firm.com',
            Action__c = 'TRADE_SUBMITTED',
            Gate_Trace__c = 'gate_5 hitl approval_token=SECRET_TOKEN_VALUE ok'
        );
        Boolean err = false;
        try { insert row; } catch (DmlException e) { err = true; }
        System.assert(err, 'Raw approval_token must be rejected');
    }

    @isTest static void accepts_hashed_approval_token() {
        IR_Audit_Log__c row = new IR_Audit_Log__c(
            Principal_Id__c = 'rm@firm.com',
            Action__c = 'TRADE_SUBMITTED',
            Gate_Trace__c = 'gate_5 hitl approval_token_hash=0123abcd ok'
        );
        insert row;
        System.assertNotEquals(null, row.Id);
    }

    @isTest static void non_senior_cannot_update() {
        IR_Audit_Log__c row = new IR_Audit_Log__c(Principal_Id__c = 'x', Action__c = 'ADVISORY_QUERY');
        insert row;
        row.Gate_Trace__c = 'tamper';
        Boolean err = false;
        try { update row; } catch (DmlException e) { err = true; }
        System.assert(err);
    }
}
