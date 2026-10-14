@isTest
private class SoqlSafeTest {
    @isTest static void identifier_ok() {
        System.assertEquals('Research_Brief__c', SoqlSafe.validateIdentifier('Research_Brief__c'));
    }
    @isTest static void identifier_rejects_semicolon() {
        Boolean err = false;
        try { SoqlSafe.validateIdentifier('DROP TABLE;'); } catch (SoqlSafe.SoqlSafeException e) { err = true; }
        System.assert(err);
    }
    @isTest static void escape_literal_null() { System.assertEquals('null', SoqlSafe.escapeLiteral(null)); }
    @isTest static void escape_literal_true() { System.assertEquals('true', SoqlSafe.escapeLiteral(true)); }
    @isTest static void escape_literal_number() { System.assertEquals('42', SoqlSafe.escapeLiteral(42)); }
    @isTest static void ensure_read_only_rejects_delete() {
        Boolean err = false;
        try { SoqlSafe.ensureReadOnly('SELECT Id FROM X; DELETE FROM X'); }
        catch (SoqlSafe.SoqlSafeException e) { err = true; }
        System.assert(err);
    }
    @isTest static void ensure_read_only_accepts_select() {
        SoqlSafe.ensureReadOnly('SELECT Id, Ticker__c FROM Research_Brief__c');
    }
}
