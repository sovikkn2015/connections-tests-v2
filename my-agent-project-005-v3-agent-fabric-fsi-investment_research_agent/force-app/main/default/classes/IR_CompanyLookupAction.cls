public with sharing class IR_CompanyLookupAction {

    public class LookupInput {
        @InvocableVariable(label='Company Name' description='Company name or ticker symbol to look up' required=true)
        public String companyName;
    }

    public class LookupOutput {
        @InvocableVariable(label='Company Info' description='Formatted company details including sector, exchange, market cap, and analyst coverage')
        public String companyInfo;
    }

    @InvocableMethod(
        label='Get Company Info'
        description='Returns company details including sector, exchange, market cap, and upcoming earnings'
    )
    public static List<LookupOutput> getCompanyInfo(List<LookupInput> inputs) {
        List<LookupOutput> outputs = new List<LookupOutput>();
        Long startTime = System.currentTimeMillis();

        // Langfuse tracing
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'company_lookup',
                inputs[0].companyName,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (LookupInput input : inputs) {
            LookupOutput output = new LookupOutput();
            try {
                String searchTerm = input.companyName != null ? input.companyName.trim() : '';
                if (String.isBlank(searchTerm)) {
                    output.companyInfo = 'Please provide a company name or ticker symbol.';
                    outputs.add(output);
                    continue;
                }

                IR_Company__c company = findCompany(searchTerm);

                if (company == null) {
                    output.companyInfo = 'No company found matching "' + searchTerm + '". Try a different name or ticker symbol.';
                    outputs.add(output);
                    continue;
                }

                String info = formatCompanyInfo(company);

                List<IR_Coverage__c> coverages = [
                    SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c
                    FROM IR_Coverage__c
                    WHERE Company__c = :company.Id
                    ORDER BY Analyst__c
                ];

                if (!coverages.isEmpty()) {
                    info += '\n\nAnalyst Coverage:';
                    for (IR_Coverage__c cov : coverages) {
                        info += '\n  - ' + safeStr(cov.Analyst__c)
                            + ' | Rating: ' + safeStr(cov.Rating__c)
                            + ' | Target: ' + formatCurrency(cov.Target_Price__c)
                            + ' | Updated: ' + formatDate(cov.Last_Updated__c);
                    }
                } else {
                    info += '\n\nNo analyst coverage on file.';
                }

                output.companyInfo = info;
            } catch (Exception e) {
                output.companyInfo = 'Unable to look up company information. Please try again or check the spelling.';
            }
            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'company_lookup', inputs[i].companyName,
                    null, 'CRM', null, 'Salesforce',
                    System.currentTimeMillis() - startTime
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        // Langfuse span
        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].companyInfo != null ? outputs[0].companyInfo : '');
                IR_LangfuseTracer.addSpan(
                    traceId,
                    'get_company_info',
                    inputs[0].companyName,
                    spanOutput.length() > 500 ? spanOutput.substring(0, 500) : spanOutput,
                    System.currentTimeMillis() - startTime,
                    null,
                    'Salesforce'
                );
            } catch (Exception spanEx) {
                System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
            }
        }

        return outputs;
    }

    private static IR_Company__c findCompany(String searchTerm) {
        String escaped = String.escapeSingleQuotes(searchTerm);

        // Try exact ticker match first
        List<IR_Company__c> results = [
            SELECT Id, Name, Ticker__c, Sector__c, Exchange__c, Market_Cap__c,
                   Last_Price__c, Earnings_Date__c
            FROM IR_Company__c
            WHERE Ticker__c = :escaped.toUpperCase()
            LIMIT 1
        ];
        if (!results.isEmpty()) return results[0];

        // Try name LIKE match
        String likePattern = '%' + escaped + '%';
        results = [
            SELECT Id, Name, Ticker__c, Sector__c, Exchange__c, Market_Cap__c,
                   Last_Price__c, Earnings_Date__c
            FROM IR_Company__c
            WHERE Name LIKE :likePattern
            LIMIT 1
        ];
        return results.isEmpty() ? null : results[0];
    }

    private static String formatCompanyInfo(IR_Company__c c) {
        String info = 'Company: ' + safeStr(c.Name);
        info += '\nTicker: ' + safeStr(c.Ticker__c);
        info += '\nSector: ' + safeStr(c.Sector__c);
        info += '\nExchange: ' + safeStr(c.Exchange__c);
        info += '\nMarket Cap: ' + formatCurrency(c.Market_Cap__c);
        info += '\nLast Price: ' + formatCurrency(c.Last_Price__c);
        if (c.Earnings_Date__c != null) {
            Long daysUntil = Date.today().daysBetween(c.Earnings_Date__c);
            info += '\nNext Earnings: ' + formatDate(c.Earnings_Date__c)
                + ' (' + daysUntil + ' days)';
        } else {
            info += '\nNext Earnings: Not scheduled';
        }
        return info;
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }

    private static String formatCurrency(Decimal value) {
        if (value == null) return 'N/A';
        if (value >= 1000000000000L) return '$' + (value / 1000000000000L).setScale(2) + 'T';
        if (value >= 1000000000) return '$' + (value / 1000000000).setScale(2) + 'B';
        if (value >= 1000000) return '$' + (value / 1000000).setScale(1) + 'M';
        if (value >= 1000) return '$' + (value / 1000).setScale(0) + 'K';
        return '$' + value.setScale(2);
    }

    private static String formatDate(Date d) {
        return d != null ? String.valueOf(d) : 'N/A';
    }
}
