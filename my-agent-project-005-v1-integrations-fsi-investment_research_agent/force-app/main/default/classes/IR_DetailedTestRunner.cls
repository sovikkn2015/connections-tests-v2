public with sharing class IR_DetailedTestRunner {
    public static void runAll() {
        // Company Lookup
        testCompany('NVDA');
        testCompany('AAPL');
        testCompany('JPM');
        
        // Coverage Check
        testCoverage('NVDA');
        testCoverage('Sarah Kim');
        testCoverage('Healthcare');
        
        // Earnings Calendar
        testEarnings('NVDA');
        testEarnings('this month');
        
        // Watchlist
        testWatchlist('all');
        testWatchlist('high');
        
        // Compliance
        testCompliance('NVDA');
        testCompliance('JPM');
        testCompliance('AAPL');
    }
    
    private static void testCompany(String q) {
        IR_CompanyLookupAction.LookupInput inp = new IR_CompanyLookupAction.LookupInput();
        inp.companyName = q;
        String result = IR_CompanyLookupAction.getCompanyInfo(new List<IR_CompanyLookupAction.LookupInput>{inp})[0].companyInfo;
        System.debug('TEST|company_lookup|get_company_info|' + q + '|CRM (IR_Company__c, IR_Coverage__c)|' + result.substring(0, Math.min(200, result.length())));
    }
    
    private static void testCoverage(String q) {
        IR_CoverageCheckAction.CoverageInput inp = new IR_CoverageCheckAction.CoverageInput();
        inp.query = q;
        String result = IR_CoverageCheckAction.getCoverageInfo(new List<IR_CoverageCheckAction.CoverageInput>{inp})[0].coverageInfo;
        System.debug('TEST|coverage_check|get_coverage_info|' + q + '|CRM (IR_Coverage__c)|' + result.substring(0, Math.min(200, result.length())));
    }
    
    private static void testEarnings(String q) {
        IR_EarningsCalendarAction.CalendarInput inp = new IR_EarningsCalendarAction.CalendarInput();
        inp.query = q;
        String result = IR_EarningsCalendarAction.getEarningsCalendar(new List<IR_EarningsCalendarAction.CalendarInput>{inp})[0].earningsCalendar;
        System.debug('TEST|earnings_calendar|get_earnings_calendar|' + q + '|CRM (IR_Company__c)|' + result.substring(0, Math.min(200, result.length())));
    }
    
    private static void testWatchlist(String q) {
        IR_WatchlistAction.WatchlistInput inp = new IR_WatchlistAction.WatchlistInput();
        inp.query = q;
        String result = IR_WatchlistAction.getWatchlist(new List<IR_WatchlistAction.WatchlistInput>{inp})[0].watchlistInfo;
        System.debug('TEST|watchlist|get_watchlist|' + q + '|CRM (IR_Watchlist__c)|' + result.substring(0, Math.min(200, result.length())));
    }
    
    private static void testCompliance(String q) {
        IR_ComplianceScreeningAction.ScreeningInput inp = new IR_ComplianceScreeningAction.ScreeningInput();
        inp.ticker = q;
        String result = IR_ComplianceScreeningAction.checkCompliance(new List<IR_ComplianceScreeningAction.ScreeningInput>{inp})[0].complianceResult;
        System.debug('TEST|compliance_screening|check_compliance|' + q + '|CRM (IR_Company__c)|' + result.substring(0, Math.min(200, result.length())));
    }
}
