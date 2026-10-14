public with sharing class WA_WorkbenchController {
    
    @RemoteAction
    public static String routeQuery(String query) {
        if (String.isBlank(query)) return 'Please enter a query.';
        
        String lower = query.toLowerCase();
        try {
            if (lower.contains('portfolio') || lower.contains('allocation') || lower.contains('performance') || lower.contains('return')) {
                DC_PortfolioReviewAction.ReviewInput inp = new DC_PortfolioReviewAction.ReviewInput();
                inp.clientName = cleanName(query);
                return DC_PortfolioReviewAction.getPortfolioSummary(new List<DC_PortfolioReviewAction.ReviewInput>{inp})[0].portfolioSummary;
            }
            if (lower.contains('goal') || lower.contains('retirement') || lower.contains('college') || lower.contains('saving')) {
                DC_GoalPlanningAction.GoalInput inp = new DC_GoalPlanningAction.GoalInput();
                inp.clientName = cleanName(query);
                return DC_GoalPlanningAction.getFinancialGoals(new List<DC_GoalPlanningAction.GoalInput>{inp})[0].goalsSummary;
            }
            if (lower.contains('meeting') || lower.contains('prep') || lower.contains('agenda')) {
                DC_MeetingPrepAction.PrepInput inp = new DC_MeetingPrepAction.PrepInput();
                inp.clientName = cleanName(query);
                return DC_MeetingPrepAction.getMeetingPrep(new List<DC_MeetingPrepAction.PrepInput>{inp})[0].meetingBrief;
            }
            if (lower.contains('rebalance') || lower.contains('rebalancing') || lower.contains('drift')) {
                DC_RebalancingAction.RebalanceInput inp = new DC_RebalancingAction.RebalanceInput();
                inp.clientName = cleanName(query);
                return DC_RebalancingAction.checkRebalancing(new List<DC_RebalancingAction.RebalanceInput>{inp})[0].rebalancingAnalysis;
            }
            if (lower.contains('transaction') || lower.contains('trade') || lower.contains('buy') || lower.contains('sell') || lower.contains('dividend')) {
                DC_TransactionHistoryAction.TxnInput inp = new DC_TransactionHistoryAction.TxnInput();
                inp.clientName = cleanName(query);
                return DC_TransactionHistoryAction.getTransactionHistory(new List<DC_TransactionHistoryAction.TxnInput>{inp})[0].transactionHistory;
            }
            if (lower.contains('compliance') || lower.contains('suitability') || lower.contains('concentration')) {
                DC_ComplianceCheckAction.ComplianceInput inp = new DC_ComplianceCheckAction.ComplianceInput();
                inp.clientName = cleanName(query);
                return DC_ComplianceCheckAction.runComplianceCheck(new List<DC_ComplianceCheckAction.ComplianceInput>{inp})[0].complianceReport;
            }
            if (lower.contains('referral') || lower.contains('referred')) {
                DC_ReferralTrackingAction.ReferralInput inp = new DC_ReferralTrackingAction.ReferralInput();
                inp.clientName = cleanName(query);
                return DC_ReferralTrackingAction.getReferralInfo(new List<DC_ReferralTrackingAction.ReferralInput>{inp})[0].referralInfo;
            }
            // Default: client lookup
            DC_ClientLookupAction.LookupInput inp = new DC_ClientLookupAction.LookupInput();
            inp.clientName = cleanName(query);
            return DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{inp})[0].clientSummary;
        } catch (Exception e) {
            return 'Error: ' + e.getMessage();
        }
    }
    
    private static String cleanName(String query) {
        String cleaned = query;
        cleaned = cleaned.replaceAll('(?i)^(show me|look up|get|find|tell me about|tell more about|how is|how are|what are|prep me for|prepare for|does|is the|run|check|recent|who referred)\\s+', '');
        cleaned = cleaned.replaceAll('(?i)\\s+(household|family|portfolio|goals|meeting|transactions|compliance|referral|account|client|info|history|check|alert|prep|rebalancing|needs|status|review|progress|allocation|drift|compliant|fund).*$', '');
        cleaned = cleaned.replaceAll('(?i)\\b(the|my|a|an)\\s+', '');
        cleaned = cleaned.replaceAll('(?i)\'s\\b', '');
        return cleaned.trim();
    }
}
