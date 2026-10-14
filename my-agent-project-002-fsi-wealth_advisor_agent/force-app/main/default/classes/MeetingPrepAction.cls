public with sharing class MeetingPrepAction {

    public class PrepInput {
        @InvocableVariable(label='Client Name' description='Name of the client to prepare meeting brief for' required=true)
        public String clientName;
    }

    public class PrepOutput {
        @InvocableVariable(label='Meeting Brief' description='Meeting preparation brief with client summary and talking points')
        public String meetingBrief;
    }

    @InvocableMethod(
        label='Get Meeting Prep'
        description='Returns a meeting preparation brief including client summary, recent activity, portfolio highlights, and talking points'
    )
    public static List<PrepOutput> getMeetingPrep(List<PrepInput> inputs) {
        List<PrepOutput> outputs = new List<PrepOutput>();

        for (PrepInput input : inputs) {
            PrepOutput output = new PrepOutput();
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|meeting|prep|s)\\s*', ' ')
                .trim();
            if (String.isBlank(cleanName)) cleanName = rawName;
            String searchName = '%' + cleanName + '%';

            List<WA_Client__c> clients = [
                SELECT Id, Name, Household__r.Name, Household__r.Total_AUM__c,
                    Household__r.Risk_Profile__c, Household__r.Advisor__c
                FROM WA_Client__c
                WHERE Name LIKE :searchName OR Household__r.Name LIKE :searchName
                LIMIT 1
            ];

            if (clients.isEmpty()) {
                output.meetingBrief = 'No client found matching "' + input.clientName + '".';
                outputs.add(output);
                continue;
            }

            WA_Client__c client = clients[0];

            // Get upcoming meeting
            List<WA_Meeting__c> meetings = [
                SELECT Name, Date_Time__c, Location__c, Notes__c, Action_Items__c
                FROM WA_Meeting__c
                WHERE Client__c = :client.Id AND Date_Time__c >= :DateTime.now()
                ORDER BY Date_Time__c ASC
                LIMIT 1
            ];

            // Get accounts summary
            List<WA_Financial_Account__c> accounts = [
                SELECT Name, Type__c, Balance__c, YTD_Return__c
                FROM WA_Financial_Account__c
                WHERE Client__c = :client.Id
            ];

            // Get goals
            List<WA_Financial_Goal__c> goals = [
                SELECT Name, Target_Amount__c, Current_Amount__c
                FROM WA_Financial_Goal__c
                WHERE Client__c = :client.Id
            ];

            String brief = '=== MEETING PREP BRIEF ==='
                + '\nClient: ' + client.Name
                + '\nHousehold: ' + client.Household__r.Name
                + '\nTotal AUM: $' + formatCurrency(client.Household__r.Total_AUM__c)
                + '\nRisk Profile: ' + client.Household__r.Risk_Profile__c;

            if (!meetings.isEmpty()) {
                WA_Meeting__c mtg = meetings[0];
                brief += '\n\n--- Upcoming Meeting ---'
                    + '\nSubject: ' + mtg.Name
                    + '\nDate: ' + mtg.Date_Time__c.format('MMMM d, yyyy h:mm a')
                    + '\nLocation: ' + (mtg.Location__c != null ? mtg.Location__c : 'TBD');
                if (String.isNotBlank(mtg.Notes__c)) {
                    brief += '\nNotes: ' + mtg.Notes__c;
                }
                if (String.isNotBlank(mtg.Action_Items__c)) {
                    brief += '\nOpen Action Items: ' + mtg.Action_Items__c;
                }
            } else {
                brief += '\n\nNo upcoming meetings scheduled.';
            }

            if (!accounts.isEmpty()) {
                Decimal totalBal = 0;
                brief += '\n\n--- Portfolio Snapshot ---';
                for (WA_Financial_Account__c acct : accounts) {
                    Decimal bal = acct.Balance__c != null ? acct.Balance__c : 0;
                    totalBal += bal;
                    brief += '\n  ' + acct.Name + ' (' + acct.Type__c + '): $' + formatCurrency(bal)
                        + ' | YTD: ' + (acct.YTD_Return__c != null ? acct.YTD_Return__c + '%' : 'N/A');
                }
                brief += '\n  Total: $' + formatCurrency(totalBal);
            }

            if (!goals.isEmpty()) {
                brief += '\n\n--- Goals Status ---';
                for (WA_Financial_Goal__c goal : goals) {
                    Decimal target = goal.Target_Amount__c != null ? goal.Target_Amount__c : 0;
                    Decimal current = goal.Current_Amount__c != null ? goal.Current_Amount__c : 0;
                    Decimal pct = target > 0 ? ((current / target) * 100).setScale(0) : 0;
                    brief += '\n  ' + goal.Name + ': ' + pct + '% ($' + formatCurrency(current) + ' / $' + formatCurrency(target) + ')';
                }
            }

            brief += '\n\n--- Suggested Talking Points ---'
                + '\n  1. Review portfolio performance and any rebalancing needs'
                + '\n  2. Discuss progress toward financial goals'
                + '\n  3. Address any life changes or updated priorities'
                + '\n  4. Review and confirm risk tolerance';

            output.meetingBrief = brief;
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
