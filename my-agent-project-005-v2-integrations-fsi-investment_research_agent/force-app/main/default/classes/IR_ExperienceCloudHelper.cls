/**
 * IR_ExperienceCloudHelper — Helper for Experience Cloud channel setup.
 *
 * Experience Cloud Setup Steps:
 *   1. Create Experience Cloud site (Digital Experiences > All Sites > New)
 *   2. Choose "Customer Service" or "Partner Central" template
 *   3. Add "Embedded Service" or "Einstein Bot" component in Experience Builder
 *   4. Configure component to use IR_Research_Agent
 *   5. Set up authentication (SAML SSO or Social Login)
 *   6. Create Permission Set for portal users with Read access to:
 *      IR_Company__c, IR_Coverage__c, IR_Watchlist__c, IR_Audit_Log__c
 *   7. Assign Permission Set to portal user profile
 *   8. Publish the site
 *
 * MNPI: External portal users never see CONFIDENTIAL/RESTRICTED data.
 * IR_MnpiGuard enforces this at the data layer.
 */
public with sharing class IR_ExperienceCloudHelper {

    /**
     * Returns agent configuration needed for Experience Cloud deployment.
     */
    public static Map<String, Object> getAgentConfiguration() {
        Map<String, Object> config = new Map<String, Object>();
        config.put('agentName', 'IR_Research_Agent');
        config.put('agentLabel', 'Investment Research Agent');
        config.put('channels', new List<String>{ 'Service Console', 'Experience Cloud', 'Slack' });
        config.put('requiredObjects', new List<String>{
            'IR_Company__c', 'IR_Coverage__c', 'IR_Watchlist__c',
            'IR_Audit_Log__c', 'IR_Research_Note__c'
        });
        config.put('externalTopics', new List<String>{
            'company_lookup', 'coverage_check', 'earnings_calendar',
            'market_data', 'sec_filings', 'financial_analysis', 'sentiment_analysis'
        });
        config.put('internalOnlyTopics', new List<String>{
            'compliance_screening', 'watchlist', 'research_brief'
        });
        config.put('mnpiRules', new Map<String, String>{
            'PUBLIC' => 'Available to all channels',
            'INTERNAL' => 'Internal channels only',
            'CONFIDENTIAL' => 'Never crosses platform boundary',
            'RESTRICTED' => 'Compliance role only'
        });
        config.put('experienceCloudTemplate', 'Customer Service or Partner Central');
        config.put('authenticationMethod', 'SAML SSO or Social Login');
        config.put('apiVersion', '66.0');
        return config;
    }

    /**
     * Validates that the current org has the required custom objects.
     */
    public static List<String> validateOrgSetup() {
        List<String> missing = new List<String>();
        for (String objName : new List<String>{
            'IR_Company__c', 'IR_Coverage__c', 'IR_Watchlist__c', 'IR_Audit_Log__c'
        }) {
            try {
                if (Schema.getGlobalDescribe().get(objName) == null) {
                    missing.add(objName);
                }
            } catch (Exception e) {
                missing.add(objName + ' (error: ' + e.getMessage() + ')');
            }
        }
        return missing;
    }
}
