public with sharing class ClientLookupAction {

    public class LookupInput {
        @InvocableVariable(label='Client Name' description='Name of the client or household to look up' required=true)
        public String clientName;
    }

    public class LookupOutput {
        @InvocableVariable(label='Client Summary' description='360-degree client and household summary')
        public String clientSummary;
    }

    @InvocableMethod(
        label='Get Client 360'
        description='Returns a 360-degree view of a client including household members, accounts, and AUM'
    )
    public static List<LookupOutput> getClient360(List<LookupInput> inputs) {
        List<LookupOutput> outputs = new List<LookupOutput>();

        for (LookupInput input : inputs) {
            LookupOutput output = new LookupOutput();
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            // Strip common suffixes for better fuzzy matching
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?)\\s*', ' ')
                .replaceAll('(?i)s$', '')
                .trim();
            if (String.isBlank(cleanName)) {
                cleanName = rawName;
            }
            String searchName = '%' + cleanName + '%';

            // Search households first
            List<WA_Household__c> households = [
                SELECT Id, Name, Total_AUM__c, Risk_Profile__c, Advisor__c,
                    (SELECT Id, Name, Email__c, Phone__c, Role__c FROM Clients__r)
                FROM WA_Household__c
                WHERE Name LIKE :searchName
                LIMIT 1
            ];

            if (!households.isEmpty()) {
                WA_Household__c hh = households[0];
                String summary = 'Household: ' + hh.Name
                    + '\nTotal AUM: $' + formatCurrency(hh.Total_AUM__c)
                    + '\nRisk Profile: ' + hh.Risk_Profile__c
                    + '\nAdvisor: ' + hh.Advisor__c
                    + '\n\nMembers:';

                for (WA_Client__c client : hh.Clients__r) {
                    summary += '\n  - ' + client.Name + ' (' + client.Role__c + ')'
                        + ' | ' + client.Email__c;
                }

                // Get accounts for all household members
                Set<Id> clientIds = new Set<Id>();
                for (WA_Client__c c : hh.Clients__r) {
                    clientIds.add(c.Id);
                }

                List<WA_Financial_Account__c> accounts = [
                    SELECT Name, Type__c, Balance__c
                    FROM WA_Financial_Account__c
                    WHERE Client__c IN :clientIds
                ];

                if (!accounts.isEmpty()) {
                    summary += '\n\nAccounts:';
                    for (WA_Financial_Account__c acct : accounts) {
                        summary += '\n  - ' + acct.Name + ' (' + acct.Type__c + '): $' + formatCurrency(acct.Balance__c);
                    }
                }

                output.clientSummary = summary;
            } else {
                // Try searching by client name
                List<WA_Client__c> clients = [
                    SELECT Id, Name, Role__c, Household__r.Name, Household__r.Total_AUM__c
                    FROM WA_Client__c
                    WHERE Name LIKE :searchName
                    LIMIT 1
                ];

                if (!clients.isEmpty()) {
                    WA_Client__c c = clients[0];
                    output.clientSummary = 'Client: ' + c.Name + ' (' + c.Role__c + ')'
                        + '\nHousehold: ' + c.Household__r.Name
                        + '\nHousehold AUM: $' + formatCurrency(c.Household__r.Total_AUM__c);
                } else {
                    output.clientSummary = 'No client or household found matching "' + input.clientName + '".';
                }
            }

            outputs.add(output);
        }
        return outputs;
    }

    private static String formatCurrency(Decimal value) {
        if (value == null) return '0';
        if (value >= 1000000) return String.valueOf((value / 1000000).setScale(1)) + 'M';
        if (value >= 1000) return String.valueOf((value / 1000).setScale(0)) + 'K';
        return String.valueOf(value.setScale(2));
    }
}
