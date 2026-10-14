/**
 * IR_TestRunner — Runs 19 CRM queries across all Sprint 1 Apex actions.
 * Used for end-to-end validation of the Investment Research Agent.
 *
 * Usage: IR_TestRunner.runAll();
 */
public with sharing class IR_TestRunner {

    private static Integer passed = 0;
    private static Integer failed = 0;
    private static List<String> failures = new List<String>();

    public static void runAll() {
        passed = 0;
        failed = 0;
        failures = new List<String>();

        System.debug('=== IR_TestRunner: Starting 19 CRM Query Tests ===');

        testCompanyLookup();
        testCoverageCheck();
        testEarningsCalendar();
        testWatchlist();
        testComplianceScreening();

        System.debug('');
        System.debug('=== RESULTS: ' + passed + ' passed, ' + failed + ' failed out of ' + (passed + failed) + ' ===');
        if (!failures.isEmpty()) {
            System.debug('FAILURES:');
            for (String f : failures) {
                System.debug('  - ' + f);
            }
        }
    }

    private static void testCompanyLookup() {
        List<String> tickers = new List<String>{'NVDA', 'AAPL', 'JPM', 'MSFT', 'XOM'};
        for (String ticker : tickers) {
            try {
                IR_CompanyLookupAction.LookupInput inp = new IR_CompanyLookupAction.LookupInput();
                inp.companyName = ticker;
                List<IR_CompanyLookupAction.LookupOutput> out =
                    IR_CompanyLookupAction.getCompanyInfo(new List<IR_CompanyLookupAction.LookupInput>{inp});
                String result = out[0].companyInfo;
                Boolean ok = result != null && !result.contains('Unable to look up');
                logResult('CompanyLookup[' + ticker + ']', ok, result);
            } catch (Exception e) {
                logResult('CompanyLookup[' + ticker + ']', false, 'EXCEPTION: ' + e.getMessage());
            }
        }
    }

    private static void testCoverageCheck() {
        List<String> queries = new List<String>{'NVDA', 'Sarah Kim', 'Healthcare', 'David Chen', 'AAPL'};
        for (String q : queries) {
            try {
                IR_CoverageCheckAction.CoverageInput inp = new IR_CoverageCheckAction.CoverageInput();
                inp.query = q;
                List<IR_CoverageCheckAction.CoverageOutput> out =
                    IR_CoverageCheckAction.getCoverageInfo(new List<IR_CoverageCheckAction.CoverageInput>{inp});
                String result = out[0].coverageInfo;
                Boolean ok = result != null && !result.contains('Unable to retrieve');
                logResult('CoverageCheck[' + q + ']', ok, result);
            } catch (Exception e) {
                logResult('CoverageCheck[' + q + ']', false, 'EXCEPTION: ' + e.getMessage());
            }
        }
    }

    private static void testEarningsCalendar() {
        List<String> queries = new List<String>{'NVDA', 'this month', 'all'};
        for (String q : queries) {
            try {
                IR_EarningsCalendarAction.CalendarInput inp = new IR_EarningsCalendarAction.CalendarInput();
                inp.query = q;
                List<IR_EarningsCalendarAction.CalendarOutput> out =
                    IR_EarningsCalendarAction.getEarningsCalendar(new List<IR_EarningsCalendarAction.CalendarInput>{inp});
                String result = out[0].earningsCalendar;
                Boolean ok = result != null && !result.contains('Unable to retrieve');
                logResult('EarningsCalendar[' + q + ']', ok, result);
            } catch (Exception e) {
                logResult('EarningsCalendar[' + q + ']', false, 'EXCEPTION: ' + e.getMessage());
            }
        }
    }

    private static void testWatchlist() {
        List<String> queries = new List<String>{'all', 'high', 'Sarah Kim'};
        for (String q : queries) {
            try {
                IR_WatchlistAction.WatchlistInput inp = new IR_WatchlistAction.WatchlistInput();
                inp.query = q;
                List<IR_WatchlistAction.WatchlistOutput> out =
                    IR_WatchlistAction.getWatchlist(new List<IR_WatchlistAction.WatchlistInput>{inp});
                String result = out[0].watchlistInfo;
                Boolean ok = result != null && !result.contains('Unable to retrieve');
                logResult('Watchlist[' + q + ']', ok, result);
            } catch (Exception e) {
                logResult('Watchlist[' + q + ']', false, 'EXCEPTION: ' + e.getMessage());
            }
        }
    }

    private static void testComplianceScreening() {
        List<String> tickers = new List<String>{'NVDA', 'JPM', 'AAPL'};
        for (String ticker : tickers) {
            try {
                IR_ComplianceScreeningAction.ScreeningInput inp = new IR_ComplianceScreeningAction.ScreeningInput();
                inp.ticker = ticker;
                List<IR_ComplianceScreeningAction.ScreeningOutput> out =
                    IR_ComplianceScreeningAction.checkCompliance(new List<IR_ComplianceScreeningAction.ScreeningInput>{inp});
                String result = out[0].complianceResult;
                Boolean ok = result != null && !result.contains('Unable to complete');
                logResult('Compliance[' + ticker + ']', ok, result);
            } catch (Exception e) {
                logResult('Compliance[' + ticker + ']', false, 'EXCEPTION: ' + e.getMessage());
            }
        }
    }

    private static void logResult(String testName, Boolean ok, String result) {
        String preview = result != null ? result.substring(0, Math.min(120, result.length())) : 'NULL';
        if (ok) {
            passed++;
            System.debug('PASS ' + testName + ': ' + preview);
        } else {
            failed++;
            failures.add(testName + ': ' + preview);
            System.debug('FAIL ' + testName + ': ' + preview);
        }
    }
}
