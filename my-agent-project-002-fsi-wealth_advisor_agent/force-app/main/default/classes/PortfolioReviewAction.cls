public with sharing class PortfolioReviewAction {

    public class ReviewInput {
        @InvocableVariable(label='Client Name' description='Name of the client to review portfolio for' required=true)
        public String clientName;
    }

    public class ReviewOutput {
        @InvocableVariable(label='Portfolio Summary' description='Portfolio allocation, performance, and alerts')
        public String portfolioSummary;
    }

    @InvocableMethod(
        label='Get Portfolio Summary'
        description='Returns portfolio allocation breakdown, YTD returns, and rebalancing alerts for a client'
    )
    public static List<ReviewOutput> getPortfolioSummary(List<ReviewInput> inputs) {
        List<ReviewOutput> outputs = new List<ReviewOutput>();

        for (ReviewInput input : inputs) {
            ReviewOutput output = new ReviewOutput();
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|s)\\s*', ' ')
                .trim();
            if (String.isBlank(cleanName)) cleanName = rawName;
            String searchName = '%' + cleanName + '%';

            List<WA_Client__c> clients = [
                SELECT Id, Name, Household__r.Name, Household__r.Risk_Profile__c
                FROM WA_Client__c
                WHERE Name LIKE :searchName
                LIMIT 1
            ];

            if (clients.isEmpty()) {
                output.portfolioSummary = 'No client found matching "' + input.clientName + '".';
                outputs.add(output);
                continue;
            }

            WA_Client__c client = clients[0];
            List<WA_Financial_Account__c> accounts = [
                SELECT Name, Type__c, Balance__c, Allocation__c, YTD_Return__c
                FROM WA_Financial_Account__c
                WHERE Client__c = :client.Id
            ];

            if (accounts.isEmpty()) {
                output.portfolioSummary = 'No financial accounts found for ' + client.Name + '.';
                outputs.add(output);
                continue;
            }

            Decimal totalBalance = 0;
            Decimal weightedReturn = 0;
            String summary = 'Portfolio Review: ' + client.Name
                + '\nHousehold: ' + client.Household__r.Name
                + '\nRisk Profile: ' + client.Household__r.Risk_Profile__c
                + '\n\nAccounts:';

            for (WA_Financial_Account__c acct : accounts) {
                Decimal bal = acct.Balance__c != null ? acct.Balance__c : 0;
                totalBalance += bal;
                summary += '\n  - ' + acct.Name + ' (' + acct.Type__c + ')'
                    + '\n    Balance: $' + formatCurrency(bal)
                    + '\n    Allocation: ' + acct.Allocation__c
                    + '\n    YTD Return: ' + (acct.YTD_Return__c != null ? acct.YTD_Return__c + '%' : 'N/A');
                if (acct.YTD_Return__c != null && bal > 0) {
                    weightedReturn += (acct.YTD_Return__c * bal);
                }
            }

            Decimal avgReturn = totalBalance > 0 ? (weightedReturn / totalBalance) : 0;
            summary += '\n\nTotal Portfolio Value: $' + formatCurrency(totalBalance);
            summary += '\nWeighted Avg YTD Return: ' + avgReturn.setScale(2) + '%';

            output.portfolioSummary = summary;
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
