public with sharing class IR_VerifyData {
    public static void run() {
        System.debug('=== IR AGENT DATA VERIFICATION ===');
        System.debug('IR_Company__c:       ' + [SELECT COUNT() FROM IR_Company__c] + ' (expected: 10)');
        System.debug('IR_Coverage__c:      ' + [SELECT COUNT() FROM IR_Coverage__c] + ' (expected: 20)');
        System.debug('IR_Watchlist__c:     ' + [SELECT COUNT() FROM IR_Watchlist__c] + ' (expected: 8)');
        System.debug('IR_Research_Note__c: ' + [SELECT COUNT() FROM IR_Research_Note__c] + ' (expected: 5)');
        System.debug('IR_Audit_Log__c:     ' + [SELECT COUNT() FROM IR_Audit_Log__c]);

        List<IR_Company__c> nvdaList = [SELECT Name, Ticker__c, Sector__c, Exchange__c, Market_Cap__c, Last_Price__c, Earnings_Date__c FROM IR_Company__c WHERE Ticker__c = 'NVDA' LIMIT 1];
        if (!nvdaList.isEmpty()) {
            IR_Company__c nvda = nvdaList[0];
            System.debug('SAMPLE: ' + nvda.Name + ' | ' + nvda.Ticker__c + ' | ' + nvda.Sector__c + ' | ' + nvda.Exchange__c + ' | $' + nvda.Market_Cap__c + ' | $' + nvda.Last_Price__c + ' | Earnings: ' + nvda.Earnings_Date__c);
            for (IR_Coverage__c cov : [SELECT Analyst__c, Rating__c, Target_Price__c FROM IR_Coverage__c WHERE Company__c = :nvda.Id]) {
                System.debug('  Coverage: ' + cov.Analyst__c + ' | ' + cov.Rating__c + ' | $' + cov.Target_Price__c);
            }
        } else {
            System.debug('ERROR: NVDA not found');
        }
        System.debug('=== VERIFICATION COMPLETE ===');
    }
}
