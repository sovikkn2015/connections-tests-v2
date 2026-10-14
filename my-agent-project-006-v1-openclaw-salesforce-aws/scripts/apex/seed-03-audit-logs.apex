// ============================================================================
// Seed Data Part 3 of 3 — IR_Audit_Log__c (50 records)
// Run with: sf apex run --file scripts/apex/seed-03-audit-logs.apex
// Requires: seed-01 and seed-02 to have been run first.
// ============================================================================

try {

// === 7. IR_AUDIT_LOG__c (50) — Audit trail from last 30 days ===
System.debug('=== Creating 50 IR_Audit_Log__c records ===');

DateTime baseTime = DateTime.now();
List<IR_Audit_Log__c> allLogs = new List<IR_Audit_Log__c>();

// --- Batch 1: Standard QUERY actions (15 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-29), Trace_Id__c='trc-2026-03-01-00101', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='What is the current analyst consensus on NVDA?', Data_Sources_Used__c='IR_Coverage__c, IR_Company__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-28), Trace_Id__c='trc-2026-03-02-00201', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Show me all healthcare stocks with Buy ratings', Data_Sources_Used__c='IR_Coverage__c, IR_Company__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-27), Trace_Id__c='trc-2026-03-03-00301', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='What are the upcoming earnings dates for energy sector?', Data_Sources_Used__c='IR_Watchlist__c, IR_Company__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-26), Trace_Id__c='trc-2026-03-04-00401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Compare NVDA and AMD target prices and ratings', Data_Sources_Used__c='IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-25), Trace_Id__c='trc-2026-03-05-00501', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='What is JPM current target price and thesis?', Data_Sources_Used__c='IR_Coverage__c, IR_Research_Note__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-24), Trace_Id__c='trc-2026-03-06-00601', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='List all stocks on watchlist with High priority', Data_Sources_Used__c='IR_Watchlist__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-23), Trace_Id__c='trc-2026-03-07-00701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Show Henderson Family portfolio allocation breakdown', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-22), Trace_Id__c='trc-2026-03-08-00801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='What are the risk factors for LLY?', Data_Sources_Used__c='IR_Research_Note__c, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-21), Trace_Id__c='trc-2026-03-09-00901', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Show me all Overweight-rated stocks across my coverage', Data_Sources_Used__c='IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-20), Trace_Id__c='trc-2026-03-10-01001', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='What is the total market cap of my tech coverage universe?', Data_Sources_Used__c='IR_Company__c, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-19), Trace_Id__c='trc-2026-03-11-01101', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Show Nakamura Trust bond allocation details', Data_Sources_Used__c='Account'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-18), Trace_Id__c='trc-2026-03-12-01201', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='What catalysts are upcoming for CAT and HON?', Data_Sources_Used__c='IR_Watchlist__c, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-17), Trace_Id__c='trc-2026-03-13-01301', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate a sector heatmap for technology coverage', Data_Sources_Used__c='IR_Coverage__c, IR_Company__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-16), Trace_Id__c='trc-2026-03-14-01401', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Compare GS and MS on valuation metrics', Data_Sources_Used__c='IR_Coverage__c, IR_Company__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-15), Trace_Id__c='trc-2026-03-15-01501', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Show Reeves Retirement glide path allocation', Data_Sources_Used__c='Account'));

// --- Batch 2: RESEARCH_BRIEF actions (10 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-14), Trace_Id__c='trc-2026-03-16-01601', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate research brief for NVDA', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-13), Trace_Id__c='trc-2026-03-17-01701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate research brief for AAPL', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-12), Trace_Id__c='trc-2026-03-18-01801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate research brief for JPM', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-11), Trace_Id__c='trc-2026-03-19-01901', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate research brief for LLY', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-10), Trace_Id__c='trc-2026-03-20-02001', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Generate research brief for XOM', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-9), Trace_Id__c='trc-2026-03-21-02101', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Update NVDA brief with latest earnings data', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, IR_Research_Note__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-8), Trace_Id__c='trc-2026-03-22-02201', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate comparative brief for BAC vs WFC', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-7), Trace_Id__c='trc-2026-03-23-02301', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Generate brief for COST ahead of earnings', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-6), Trace_Id__c='trc-2026-03-24-02401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate brief for META with Reels monetization focus', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-5), Trace_Id__c='trc-2026-03-25-02501', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate brief for ABBV immunology franchise update', Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c'));

// --- Batch 3: COMPLIANCE_CHECK actions (8 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-14), Trace_Id__c='trc-2026-03-16-02601', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Pre-trade compliance check: Henderson NVDA position sizing', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-13), Trace_Id__c='trc-2026-03-17-02701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Concentration alert: Henderson tech allocation review', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-12), Trace_Id__c='trc-2026-03-18-02801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Pre-trade compliance check: Nakamura bond rebalance', Data_Sources_Used__c='Account'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-11), Trace_Id__c='trc-2026-03-19-02901', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Concentration alert: Singh NVDA position at 12%', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-10), Trace_Id__c='trc-2026-03-20-03001', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Concentration alert: Blackwood NVDA position at 14%', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-9), Trace_Id__c='trc-2026-03-21-03101', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Pre-trade compliance check: Reeves retirement glide path', Data_Sources_Used__c='Account'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-8), Trace_Id__c='trc-2026-03-22-03201', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Restricted list check before XOM trade recommendation', Data_Sources_Used__c='IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-7), Trace_Id__c='trc-2026-03-23-03301', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Quarterly suitability review: Morrison Capital portfolio', Data_Sources_Used__c='Account, IR_Coverage__c'));

// --- Batch 4: TRADE_REVIEW actions (5 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-6), Trace_Id__c='trc-2026-03-24-03401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Review proposed NVDA add for Henderson Family', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-5), Trace_Id__c='trc-2026-03-25-03501', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Review proposed LLY position for Ashford FO', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-4), Trace_Id__c='trc-2026-03-26-03601', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Review proposed XOM trim for Great Lakes Pension', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-3), Trace_Id__c='trc-2026-03-27-03701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Review proposed MSFT add for Meridian FO', Data_Sources_Used__c='Account, IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-2), Trace_Id__c='trc-2026-03-28-03801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Review proposed JPM position increase for Sunbelt Endowment', Data_Sources_Used__c='Account, IR_Coverage__c'));

// --- Batch 5: DATA_ACCESS actions (5 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-15), Trace_Id__c='trc-2026-03-15-03901', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='SEC EDGAR 10-K retrieval for NVDA', Data_Sources_Used__c='SEC EDGAR MCP'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-14), Trace_Id__c='trc-2026-03-16-04001', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Alpha Vantage real-time quote for JPM', Data_Sources_Used__c='Alpha Vantage MCP'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-13), Trace_Id__c='trc-2026-03-17-04101', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Tavily news search for XOM Pioneer integration', Data_Sources_Used__c='Tavily News MCP'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-12), Trace_Id__c='trc-2026-03-18-04201', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='SEC EDGAR 8-K retrieval for MSFT', Data_Sources_Used__c='SEC EDGAR MCP'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-11), Trace_Id__c='trc-2026-03-19-04301', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Alpha Vantage historical data for LLY', Data_Sources_Used__c='Alpha Vantage MCP'));

// --- Batch 6: MNPI VIOLATIONS — 3 entries (queries that attempted MNPI access) ---
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-4), Trace_Id__c='trc-2026-03-26-04401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='What are the pending NVDA insider transactions before earnings?', Data_Sources_Used__c='IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-3), Trace_Id__c='trc-2026-03-27-04501', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Show me NVDA preliminary revenue figures ahead of announcement', Data_Sources_Used__c='IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-2), Trace_Id__c='trc-2026-03-28-04601', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='What is MSFT unannounced acquisition target?', Data_Sources_Used__c='IR_Coverage__c'));

// --- Batch 7: RESTRICTED_LIST_ADD — 3 entries for TSLA, GS, PFE ---
allLogs.add(new IR_Audit_Log__c(Action__c='RESTRICTED_LIST_ADD', Timestamp__c=baseTime.addDays(-10), Trace_Id__c='trc-2026-03-20-04701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Add TSLA to restricted list — pending corporate action', Data_Sources_Used__c='IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESTRICTED_LIST_ADD', Timestamp__c=baseTime.addDays(-8), Trace_Id__c='trc-2026-03-22-04801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Add GS to restricted list — firm involvement in advisory mandate', Data_Sources_Used__c='IR_Coverage__c'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESTRICTED_LIST_ADD', Timestamp__c=baseTime.addDays(-6), Trace_Id__c='trc-2026-03-24-04901', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Add PFE to restricted list — material non-public clinical trial data', Data_Sources_Used__c='IR_Coverage__c'));

// --- Entry 50: Standard query to round out to 50 ---
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-1), Trace_Id__c='trc-2026-03-29-05001', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Show me the full coverage universe with latest ratings', Data_Sources_Used__c='IR_Coverage__c, IR_Company__c'));

insert allLogs;
System.debug('Inserted ' + allLogs.size() + ' IR_Audit_Log__c records.');

// === SUMMARY ===
System.debug('============================================');
System.debug('=== SEED PART 3 COMPLETE ===');
System.debug('  IR_Audit_Log__c:   ' + allLogs.size());
System.debug('============================================');
System.debug('Design decisions embedded in data:');
System.debug('  - Henderson: 60% tech allocation (aggressive growth)');
System.debug('  - Nakamura: 40% bonds (conservative)');
System.debug('  - Reeves: near-retirement glide path');
System.debug('  - Henderson/Singh/Blackwood: >10% NVDA concentration');
System.debug('  - MNPI violations: NVDA (2), MSFT (1) — Compliance FAIL');
System.debug('  - Restricted list: TSLA, GS, PFE');
System.debug('============================================');

} catch (Exception e) {
    System.debug(LoggingLevel.ERROR, '=== SEED PART 3 ERROR ===');
    System.debug(LoggingLevel.ERROR, 'Message: ' + e.getMessage());
    System.debug(LoggingLevel.ERROR, 'Type: ' + e.getTypeName());
    System.debug(LoggingLevel.ERROR, 'Stack: ' + e.getStackTraceString());
    throw e;
}
