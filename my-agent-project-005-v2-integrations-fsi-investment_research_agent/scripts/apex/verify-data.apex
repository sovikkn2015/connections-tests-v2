// Verify seed data for Investment Research Agent — Sprint 1
// Run: sf apex run --file scripts/apex/verify-data.apex

System.debug('=== IR AGENT DATA VERIFICATION ===');

// --- Record Counts ---
Integer companyCount   = [SELECT COUNT() FROM IR_Company__c];
Integer coverageCount  = [SELECT COUNT() FROM IR_Coverage__c];
Integer watchlistCount = [SELECT COUNT() FROM IR_Watchlist__c];
Integer noteCount      = [SELECT COUNT() FROM IR_Research_Note__c];
Integer auditCount     = [SELECT COUNT() FROM IR_Audit_Log__c];

System.debug('IR_Company__c:       ' + companyCount + ' (expected: 10)');
System.debug('IR_Coverage__c:      ' + coverageCount + ' (expected: 20)');
System.debug('IR_Watchlist__c:     ' + watchlistCount + ' (expected: 8)');
System.debug('IR_Research_Note__c: ' + noteCount + ' (expected: 5)');
System.debug('IR_Audit_Log__c:     ' + auditCount);

// --- Sample Company: NVDA with Coverage ---
System.debug('\n=== SAMPLE: NVDA ===');
List<IR_Company__c> nvdaList = [
    SELECT Name, Ticker__c, Sector__c, Exchange__c, Market_Cap__c, Last_Price__c, Earnings_Date__c
    FROM IR_Company__c
    WHERE Ticker__c = 'NVDA'
    LIMIT 1
];

if (!nvdaList.isEmpty()) {
    IR_Company__c nvda = nvdaList[0];
    System.debug('Company: ' + nvda.Name);
    System.debug('  Ticker: ' + nvda.Ticker__c);
    System.debug('  Sector: ' + nvda.Sector__c);
    System.debug('  Exchange: ' + nvda.Exchange__c);
    System.debug('  Market Cap: $' + nvda.Market_Cap__c);
    System.debug('  Last Price: $' + nvda.Last_Price__c);
    System.debug('  Earnings Date: ' + nvda.Earnings_Date__c);


    // Coverage for NVDA
    System.debug('\n  Coverage:');
    for (IR_Coverage__c cov : [
        SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c
        FROM IR_Coverage__c
        WHERE Company__c = :nvda.Id
        ORDER BY Last_Updated__c DESC
    ]) {
        System.debug('    ' + cov.Analyst__c + ' — ' + cov.Rating__c + ' / $' + cov.Target_Price__c + ' (updated: ' + cov.Last_Updated__c + ')');
    }

    // Watchlist for NVDA
    System.debug('\n  Watchlist:');
    for (IR_Watchlist__c w : [
        SELECT Analyst__c, Priority__c, Reason__c
        FROM IR_Watchlist__c
        WHERE Company__c = :nvda.Id
    ]) {
        System.debug('    ' + w.Analyst__c + ' — ' + w.Priority__c + ' — ' + w.Reason__c);
    }

    // Research Notes for NVDA
    System.debug('\n  Research Notes:');
    for (IR_Research_Note__c n : [
        SELECT Name, Analyst__c, Rating__c, Status__c, Summary__c
        FROM IR_Research_Note__c
        WHERE Company__c = :nvda.Id
    ]) {
        System.debug('    ' + n.Name + ' (' + n.Status__c + ') — ' + n.Analyst__c + ' / ' + n.Rating__c);
        System.debug('    Summary: ' + n.Summary__c);
    }
} else {
    System.debug('ERROR: NVDA not found in IR_Company__c');
}

System.debug('\n=== VERIFICATION COMPLETE ===');
