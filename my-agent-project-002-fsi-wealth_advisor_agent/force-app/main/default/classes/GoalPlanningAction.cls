public with sharing class GoalPlanningAction {

    public class GoalInput {
        @InvocableVariable(label='Client Name' description='Name of the client or household to get goals for' required=true)
        public String clientName;
    }

    public class GoalOutput {
        @InvocableVariable(label='Goals Summary' description='Financial goals with progress and gap analysis')
        public String goalsSummary;
    }

    @InvocableMethod(
        label='Get Financial Goals'
        description='Returns financial goals with target amounts, current progress, and gap analysis for a client'
    )
    public static List<GoalOutput> getFinancialGoals(List<GoalInput> inputs) {
        List<GoalOutput> outputs = new List<GoalOutput>();

        for (GoalInput input : inputs) {
            GoalOutput output = new GoalOutput();
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|s)\\s*', ' ')
                .trim();
            if (String.isBlank(cleanName)) cleanName = rawName;
            String searchName = '%' + cleanName + '%';

            // Find clients matching the name (could be household or individual)
            List<WA_Client__c> clients = [
                SELECT Id, Name, Household__r.Name
                FROM WA_Client__c
                WHERE Name LIKE :searchName OR Household__r.Name LIKE :searchName
                LIMIT 5
            ];

            if (clients.isEmpty()) {
                output.goalsSummary = 'No client or household found matching "' + input.clientName + '".';
                outputs.add(output);
                continue;
            }

            Set<Id> clientIds = new Set<Id>();
            String householdName = '';
            for (WA_Client__c c : clients) {
                clientIds.add(c.Id);
                if (String.isNotBlank(c.Household__r.Name)) {
                    householdName = c.Household__r.Name;
                }
            }

            List<WA_Financial_Goal__c> goals = [
                SELECT Name, Target_Amount__c, Current_Amount__c, Target_Date__c, Client__r.Name
                FROM WA_Financial_Goal__c
                WHERE Client__c IN :clientIds
                ORDER BY Target_Date__c ASC
            ];

            if (goals.isEmpty()) {
                output.goalsSummary = 'No financial goals found for "' + input.clientName + '".';
                outputs.add(output);
                continue;
            }

            String summary = 'Financial Goals: ' + (String.isNotBlank(householdName) ? householdName : input.clientName)
                + '\n';

            for (WA_Financial_Goal__c goal : goals) {
                Decimal target = goal.Target_Amount__c != null ? goal.Target_Amount__c : 0;
                Decimal current = goal.Current_Amount__c != null ? goal.Current_Amount__c : 0;
                Decimal progress = target > 0 ? ((current / target) * 100).setScale(1) : 0;
                Decimal gap = target - current;

                summary += '\n  ' + goal.Name + ' (' + goal.Client__r.Name + ')'
                    + '\n    Target: $' + formatCurrency(target)
                    + '\n    Current: $' + formatCurrency(current)
                    + '\n    Progress: ' + progress + '%'
                    + '\n    Gap: $' + formatCurrency(gap)
                    + '\n    Target Date: ' + (goal.Target_Date__c != null ? String.valueOf(goal.Target_Date__c) : 'Not set');
            }

            output.goalsSummary = summary;
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
