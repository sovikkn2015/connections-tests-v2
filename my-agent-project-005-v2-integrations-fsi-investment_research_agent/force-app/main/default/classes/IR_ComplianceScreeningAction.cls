/**
 * IR_ComplianceScreeningAction — Sprint 1 CRM-only compliance screening.
 *
 * Checks three compliance dimensions for a given ticker:
 *   1. Restricted list — is the stock on the firm's restricted trading list?
 *   2. Trading window — is the company in a quiet period (earnings within 14 days)?
 *   3. MNPI check — any material non-public information flags on file?
 *
 * For Sprint 1 demo purposes:
 *   - Restricted list uses obviously fake tickers so real ones always pass
 *   - Quiet period checks earnings date proximity from IR_Company__c
 *   - MNPI always returns clean (no flags)
 *
 * Cross-platform compliance (AWS Bedrock checks) coming in Sprint 3.
 */
public with sharing class IR_ComplianceScreeningAction {

    public class ScreeningInput {
        @InvocableVariable(label='Ticker' description='Stock ticker symbol to screen for compliance' required=true)
        public String ticker;
    }

    public class ScreeningOutput {
        @InvocableVariable(label='Compliance Result' description='Formatted compliance screening report')
        public String complianceResult;
    }

    // Configurable restricted list — loaded from Custom Metadata or hardcoded fallback.
    private static final Set<String> RESTRICTED_LIST = loadRestrictedList();
    private static final Integer QUIET_PERIOD_DAYS = 14;

    private static Set<String> loadRestrictedList() {
        Set<String> tickers = new Set<String>();
        try {
            List<SObject> mdtRecords = Database.query(
                'SELECT DeveloperName FROM IR_Restricted_Ticker__mdt WHERE Is_Active__c = true'
            );
            for (SObject rec : mdtRecords) {
                tickers.add(((String) rec.get('DeveloperName')).toUpperCase());
            }
        } catch (Exception e) {
            // Fallback: demo restricted tickers
            tickers.add('RESTRICTED_TICKER_1');
            tickers.add('RESTRICTED_TICKER_2');
        }
        if (tickers.isEmpty()) {
            tickers.add('RESTRICTED_TICKER_1');
            tickers.add('RESTRICTED_TICKER_2');
        }
        return tickers;
    }

    @InvocableMethod(
        label='Check Compliance'
        description='Screens a stock ticker for restricted list, trading window, and MNPI compliance'
    )
    public static List<ScreeningOutput> checkCompliance(List<ScreeningInput> inputs) {
        Long startTime = DateTime.now().getTime();
        List<ScreeningOutput> outputs = new List<ScreeningOutput>();

        // Langfuse tracing
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'compliance_screening',
                inputs[0].ticker,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (ScreeningInput input : inputs) {
            ScreeningOutput output = new ScreeningOutput();
            try {
                String ticker = input.ticker != null ? input.ticker.trim().toUpperCase() : '';
                output.complianceResult = runScreening(ticker);
            } catch (Exception e) {
                output.complianceResult = 'Unable to complete compliance screening for "'
                    + input.ticker + '". Please try again or contact compliance.';
            }
            outputs.add(output);
        }

        // Audit logging
        Long durationMs = DateTime.now().getTime() - startTime;
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent',
                    'compliance_screening',
                    inputs[i].ticker,
                    UserInfo.getName(),
                    'CRM',
                    null,
                    'Salesforce',
                    durationMs
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        // Langfuse span
        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].complianceResult != null ? outputs[0].complianceResult : '');
                IR_LangfuseTracer.addSpan(
                    traceId,
                    'check_compliance',
                    inputs[0].ticker,
                    spanOutput.length() > 500 ? spanOutput.substring(0, 500) : spanOutput,
                    durationMs,
                    null,
                    'Salesforce'
                );
            } catch (Exception spanEx) {
                System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
            }
        }

        return outputs;
    }


    private static String runScreening(String ticker) {
        if (String.isBlank(ticker)) {
            return 'No ticker provided. Please specify a stock ticker symbol (e.g., NVDA, AAPL).';
        }

        String report = '=== COMPLIANCE SCREENING REPORT ==='
            + '\nTicker: ' + ticker
            + '\nScreened By: ' + UserInfo.getName()
            + '\nDate: ' + DateTime.now().format('yyyy-MM-dd HH:mm:ss z');

        Boolean overallPass = true;
        List<String> flags = new List<String>();

        // --- Check 1: Restricted List ---
        report += '\n\n--- 1. RESTRICTED LIST CHECK ---';
        if (RESTRICTED_LIST.contains(ticker)) {
            report += '\n  ❌ FAIL — ' + ticker + ' is on the firm restricted trading list.';
            report += '\n  Action Required: Trading is prohibited. Contact Compliance for details.';
            flags.add('Restricted list: ' + ticker + ' is restricted');
            overallPass = false;
        } else {
            report += '\n  ✅ PASS — ' + ticker + ' is not on the restricted list.';
        }

        // --- Check 2: Trading Window / Quiet Period ---
        report += '\n\n--- 2. TRADING WINDOW CHECK ---';
        List<IR_Company__c> companies = [
            SELECT Name, Ticker__c, Earnings_Date__c
            FROM IR_Company__c
            WHERE Ticker__c = :ticker
            LIMIT 1
        ];

        if (!companies.isEmpty() && companies[0].Earnings_Date__c != null) {
            IR_Company__c company = companies[0];
            Date earningsDate = company.Earnings_Date__c;
            Integer daysUntilEarnings = Date.today().daysBetween(earningsDate);

            if (daysUntilEarnings >= 0 && daysUntilEarnings <= QUIET_PERIOD_DAYS) {
                report += '\n  ⚠️ QUIET PERIOD — ' + company.Name + ' reports earnings on '
                    + earningsDate.format() + ' (' + daysUntilEarnings + ' days away).';
                report += '\n  Trading window is restricted. Pre-clearance required for any trades.';
                flags.add('Quiet period: earnings in ' + daysUntilEarnings + ' days');
                overallPass = false;
            } else if (daysUntilEarnings > QUIET_PERIOD_DAYS) {
                report += '\n  ✅ PASS — ' + company.Name + ' earnings on ' + earningsDate.format()
                    + ' (' + daysUntilEarnings + ' days away). Outside quiet period.';
            } else {
                report += '\n  ✅ PASS — ' + company.Name + ' earnings date has passed. No active quiet period.';
            }
        } else if (!companies.isEmpty()) {
            report += '\n  ℹ️ INFO — No earnings date on file for ' + ticker + '. No quiet period restriction.';
        } else {
            report += '\n  ℹ️ INFO — ' + ticker + ' not found in CRM. Unable to check earnings window.';
        }

        // --- Check 3: MNPI Check ---
        report += '\n\n--- 3. MNPI CHECK ---';
        Boolean hasMnpiFlags = IR_MnpiGuard.hasActiveMnpiFlags(ticker);
        if (hasMnpiFlags) {
            report += '\n  ⚠️ MNPI FLAG — Active MNPI flags detected for ' + ticker + '.';
            report += '\n  Material non-public information is on file.';
            report += '\n  Enhanced trading restrictions apply. Compliance review required.';
            flags.add('MNPI: Active flags detected for ' + ticker);
            overallPass = false;
        } else {
            DateTime mnpiCutoff = DateTime.now().addDays(-7);
            // Query__c is LongTextArea (not filterable). Filter by Action__c + Timestamp__c,
            // then check Query__c in Apex.
            List<IR_Audit_Log__c> mnpiCandidates = [
                SELECT Id, Action__c, Timestamp__c, Query__c
                FROM IR_Audit_Log__c
                WHERE (Action__c = 'mnpi_block' OR Action__c = 'mnpi_flag')
                  AND Timestamp__c >= :mnpiCutoff
                LIMIT 100
            ];
            List<IR_Audit_Log__c> recentMnpi = new List<IR_Audit_Log__c>();
            for (IR_Audit_Log__c c : mnpiCandidates) {
                if (c.Query__c != null && c.Query__c.toUpperCase().contains(ticker)) {
                    recentMnpi.add(c);
                    if (recentMnpi.size() >= 5) break;
                }
            }
            if (!recentMnpi.isEmpty()) {
                report += '\n  ℹ️ INFO — ' + recentMnpi.size() + ' recent MNPI-related audit entries for ' + ticker + '.';
                report += '\n  No active flags, but recent activity noted. Proceed with caution.';
            } else {
                report += '\n  ✅ PASS — No MNPI flags on file for ' + ticker + '.';
            }
        }

        // --- Overall Result ---
        report += '\n\n=== RESULT ===';
        if (overallPass) {
            report += '\n✅ CLEARED — ' + ticker + ' passes all compliance checks. Trading permitted.';
        } else {
            report += '\n⚠️ FLAGGED — ' + flags.size() + ' issue(s) found:';
            for (Integer i = 0; i < flags.size(); i++) {
                report += '\n  ' + (i + 1) + '. ' + flags[i];
            }
            report += '\nContact Compliance before proceeding with any trades.';
        }

        return report;
    }
}
