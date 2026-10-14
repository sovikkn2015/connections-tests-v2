// Test all DC_* Data Cloud actions (Projects 3 & 4)
// Run: sf apex run --file scripts/test-dc-actions.apex --target-org new-org

System.debug('========== DC ACTIONS TEST (Data Cloud) ==========');
Integer passed = 0;
Integer failed = 0;

// 1. DC_ClientLookupAction — "Tell me about the Johnsons"
try {
    DC_ClientLookupAction.LookupInput i1 = new DC_ClientLookupAction.LookupInput();
    i1.clientName = 'Johnson';
    List<DC_ClientLookupAction.LookupOutput> o1 = DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{i1});
    String r1 = o1[0].clientSummary;
    if (r1 != null && r1.contains('Johnson')) { passed++; System.debug('PASS|DC_ClientLookup|Johnson|' + r1.left(200)); }
    else { failed++; System.debug('FAIL|DC_ClientLookup|Johnson|' + r1); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_ClientLookup|Johnson|' + e.getMessage()); }

// 2. DC_ClientLookupAction — "Who is Wei Chen?"
try {
    DC_ClientLookupAction.LookupInput i2 = new DC_ClientLookupAction.LookupInput();
    i2.clientName = 'Wei Chen';
    List<DC_ClientLookupAction.LookupOutput> o2 = DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{i2});
    String r2 = o2[0].clientSummary;
    if (r2 != null && r2.contains('Chen')) { passed++; System.debug('PASS|DC_ClientLookup|Wei Chen|' + r2.left(200)); }
    else { failed++; System.debug('FAIL|DC_ClientLookup|Wei Chen|' + r2); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_ClientLookup|Wei Chen|' + e.getMessage()); }

// 3. DC_PortfolioReviewAction — "How is Sarah Johnson's portfolio?"
try {
    DC_PortfolioReviewAction.ReviewInput i3 = new DC_PortfolioReviewAction.ReviewInput();
    i3.clientName = 'Sarah Johnson';
    List<DC_PortfolioReviewAction.ReviewOutput> o3 = DC_PortfolioReviewAction.getPortfolioSummary(new List<DC_PortfolioReviewAction.ReviewInput>{i3});
    String r3 = o3[0].portfolioSummary;
    if (r3 != null && (r3.contains('Johnson') || r3.contains('IRA'))) { passed++; System.debug('PASS|DC_PortfolioReview|Sarah Johnson|' + r3.left(200)); }
    else { failed++; System.debug('FAIL|DC_PortfolioReview|Sarah Johnson|' + r3); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_PortfolioReview|Sarah Johnson|' + e.getMessage()); }

// 4. DC_GoalPlanningAction — "What are the Patels' goals?"
try {
    DC_GoalPlanningAction.GoalInput i4 = new DC_GoalPlanningAction.GoalInput();
    i4.clientName = 'Patel';
    List<DC_GoalPlanningAction.GoalOutput> o4 = DC_GoalPlanningAction.getFinancialGoals(new List<DC_GoalPlanningAction.GoalInput>{i4});
    String r4 = o4[0].goalsSummary;
    if (r4 != null && r4.contains('Patel')) { passed++; System.debug('PASS|DC_GoalPlanning|Patel|' + r4.left(200)); }
    else { failed++; System.debug('FAIL|DC_GoalPlanning|Patel|' + r4); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_GoalPlanning|Patel|' + e.getMessage()); }

// 5. DC_MeetingPrepAction — "Prep me for my meeting with Carlos"
try {
    DC_MeetingPrepAction.PrepInput i5 = new DC_MeetingPrepAction.PrepInput();
    i5.clientName = 'Carlos';
    List<DC_MeetingPrepAction.PrepOutput> o5 = DC_MeetingPrepAction.getMeetingPrep(new List<DC_MeetingPrepAction.PrepInput>{i5});
    String r5 = o5[0].meetingBrief;
    if (r5 != null && r5.contains('Martinez')) { passed++; System.debug('PASS|DC_MeetingPrep|Carlos|' + r5.left(200)); }
    else { failed++; System.debug('FAIL|DC_MeetingPrep|Carlos|' + r5); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_MeetingPrep|Carlos|' + e.getMessage()); }

// 6. DC_RebalancingAction — "Does Sarah Johnson need rebalancing?"
try {
    DC_RebalancingAction.RebalanceInput i6 = new DC_RebalancingAction.RebalanceInput();
    i6.clientName = 'Sarah Johnson';
    List<DC_RebalancingAction.RebalanceOutput> o6 = DC_RebalancingAction.checkRebalancing(new List<DC_RebalancingAction.RebalanceInput>{i6});
    String r6 = o6[0].rebalancingAnalysis;
    if (r6 != null && r6.length() > 10) { passed++; System.debug('PASS|DC_Rebalancing|Sarah Johnson|' + r6.left(200)); }
    else { failed++; System.debug('FAIL|DC_Rebalancing|Sarah Johnson|' + r6); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_Rebalancing|Sarah Johnson|' + e.getMessage()); }

// 7. DC_TransactionHistoryAction — "Show me recent transactions for Wei Chen"
try {
    DC_TransactionHistoryAction.TxnInput i7 = new DC_TransactionHistoryAction.TxnInput();
    i7.clientName = 'Wei Chen';
    List<DC_TransactionHistoryAction.TxnOutput> o7 = DC_TransactionHistoryAction.getTransactionHistory(new List<DC_TransactionHistoryAction.TxnInput>{i7});
    String r7 = o7[0].transactionHistory;
    if (r7 != null && (r7.contains('NVDA') || r7.contains('transaction') || r7.contains('Chen'))) { passed++; System.debug('PASS|DC_TransactionHistory|Wei Chen|' + r7.left(200)); }
    else { failed++; System.debug('FAIL|DC_TransactionHistory|Wei Chen|' + r7); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_TransactionHistory|Wei Chen|' + e.getMessage()); }

// 8. DC_ComplianceCheckAction — "Is the Patel account compliant?"
try {
    DC_ComplianceCheckAction.ComplianceInput i8 = new DC_ComplianceCheckAction.ComplianceInput();
    i8.clientName = 'Patel';
    List<DC_ComplianceCheckAction.ComplianceOutput> o8 = DC_ComplianceCheckAction.runComplianceCheck(new List<DC_ComplianceCheckAction.ComplianceInput>{i8});
    String r8 = o8[0].complianceReport;
    if (r8 != null && r8.length() > 10) { passed++; System.debug('PASS|DC_ComplianceCheck|Patel|' + r8.left(200)); }
    else { failed++; System.debug('FAIL|DC_ComplianceCheck|Patel|' + r8); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_ComplianceCheck|Patel|' + e.getMessage()); }

// 9. DC_ReferralTrackingAction — "Who referred the Williams family?"
try {
    DC_ReferralTrackingAction.ReferralInput i9 = new DC_ReferralTrackingAction.ReferralInput();
    i9.clientName = 'Williams';
    List<DC_ReferralTrackingAction.ReferralOutput> o9 = DC_ReferralTrackingAction.getReferralInfo(new List<DC_ReferralTrackingAction.ReferralInput>{i9});
    String r9 = o9[0].referralInfo;
    if (r9 != null && (r9.contains('Williams') || r9.contains('LinkedIn'))) { passed++; System.debug('PASS|DC_ReferralTracking|Williams|' + r9.left(200)); }
    else { failed++; System.debug('FAIL|DC_ReferralTracking|Williams|' + r9); }
} catch (Exception e) { failed++; System.debug('ERROR|DC_ReferralTracking|Williams|' + e.getMessage()); }

System.debug('========== RESULTS: ' + passed + ' passed, ' + failed + ' failed ==========');
