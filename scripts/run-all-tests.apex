// ============================================================
// COMPREHENSIVE TEST SUITE — All Projects, All Actions
// ============================================================
// Run: sf apex run --file scripts/run-all-tests.apex --target-org new-org

Long startTime = System.currentTimeMillis();

// ============================================================
// PROJECT 1: Hello World Agent — HelloAction
// ============================================================
System.debug('========== PROJECT 1: HELLO WORLD ==========');

// Test 1.1: Greeting with name
Long t1 = System.currentTimeMillis();
HelloAction.GreetingInput hi1 = new HelloAction.GreetingInput();
hi1.userName = 'Sam';
List<HelloAction.GreetingOutput> ho1 = HelloAction.getGreeting(new List<HelloAction.GreetingInput>{hi1});
Long d1 = System.currentTimeMillis() - t1;
System.debug('TEST_1.1|HelloAction|greeting_with_name|Sam|' + d1 + 'ms|' + (ho1[0].greetingMessage != null ? 'PASS' : 'FAIL') + '|' + ho1[0].greetingMessage);

// Test 1.2: Greeting without name
Long t2 = System.currentTimeMillis();
HelloAction.GreetingInput hi2 = new HelloAction.GreetingInput();
hi2.userName = '';
List<HelloAction.GreetingOutput> ho2 = HelloAction.getGreeting(new List<HelloAction.GreetingInput>{hi2});
Long d2 = System.currentTimeMillis() - t2;
System.debug('TEST_1.2|HelloAction|greeting_no_name||' + d2 + 'ms|' + (ho2[0].greetingMessage != null ? 'PASS' : 'FAIL') + '|' + ho2[0].greetingMessage);

// ============================================================
// PROJECT 2: WA CRM — SOQL-based actions
// ============================================================
System.debug('========== PROJECT 2: WA CRM (SOQL) ==========');

// Test 2.1: ClientLookupAction — household search
Long t3 = System.currentTimeMillis();
ClientLookupAction.LookupInput ci1 = new ClientLookupAction.LookupInput();
ci1.clientName = 'Johnson';
List<ClientLookupAction.LookupOutput> co1 = ClientLookupAction.getClient360(new List<ClientLookupAction.LookupInput>{ci1});
Long d3 = System.currentTimeMillis() - t3;
Boolean p3 = co1[0].clientSummary != null && co1[0].clientSummary.contains('Johnson Family');
System.debug('TEST_2.1|ClientLookupAction|household_search|Johnson|' + d3 + 'ms|' + (p3 ? 'PASS' : 'FAIL') + '|' + co1[0].clientSummary);

// Test 2.2: ClientLookupAction — individual client search
Long t4 = System.currentTimeMillis();
ClientLookupAction.LookupInput ci2 = new ClientLookupAction.LookupInput();
ci2.clientName = 'Wei Chen';
List<ClientLookupAction.LookupOutput> co2 = ClientLookupAction.getClient360(new List<ClientLookupAction.LookupInput>{ci2});
Long d4 = System.currentTimeMillis() - t4;
Boolean p4 = co2[0].clientSummary != null && co2[0].clientSummary.contains('Chen');
System.debug('TEST_2.2|ClientLookupAction|individual_search|Wei Chen|' + d4 + 'ms|' + (p4 ? 'PASS' : 'FAIL') + '|' + co2[0].clientSummary);

// Test 2.3: ClientLookupAction — not found
Long t5 = System.currentTimeMillis();
ClientLookupAction.LookupInput ci3 = new ClientLookupAction.LookupInput();
ci3.clientName = 'Nonexistent Person';
List<ClientLookupAction.LookupOutput> co3 = ClientLookupAction.getClient360(new List<ClientLookupAction.LookupInput>{ci3});
Long d5 = System.currentTimeMillis() - t5;
Boolean p5 = co3[0].clientSummary != null && co3[0].clientSummary.contains('No client');
System.debug('TEST_2.3|ClientLookupAction|not_found|Nonexistent Person|' + d5 + 'ms|' + (p5 ? 'PASS' : 'FAIL') + '|' + co3[0].clientSummary);

// Test 2.4: PortfolioReviewAction — Wei Chen
Long t6 = System.currentTimeMillis();
PortfolioReviewAction.ReviewInput pi1 = new PortfolioReviewAction.ReviewInput();
pi1.clientName = 'Wei Chen';
List<PortfolioReviewAction.ReviewOutput> po1 = PortfolioReviewAction.getPortfolioSummary(new List<PortfolioReviewAction.ReviewInput>{pi1});
Long d6 = System.currentTimeMillis() - t6;
Boolean p6 = po1[0].portfolioSummary != null && po1[0].portfolioSummary.contains('Brokerage');
System.debug('TEST_2.4|PortfolioReviewAction|portfolio_review|Wei Chen|' + d6 + 'ms|' + (p6 ? 'PASS' : 'FAIL') + '|' + po1[0].portfolioSummary);

// Test 2.5: PortfolioReviewAction — Raj Patel
Long t7 = System.currentTimeMillis();
PortfolioReviewAction.ReviewInput pi2 = new PortfolioReviewAction.ReviewInput();
pi2.clientName = 'Raj Patel';
List<PortfolioReviewAction.ReviewOutput> po2 = PortfolioReviewAction.getPortfolioSummary(new List<PortfolioReviewAction.ReviewInput>{pi2});
Long d7 = System.currentTimeMillis() - t7;
Boolean p7 = po2[0].portfolioSummary != null && po2[0].portfolioSummary.contains('Patel');
System.debug('TEST_2.5|PortfolioReviewAction|portfolio_review|Raj Patel|' + d7 + 'ms|' + (p7 ? 'PASS' : 'FAIL') + '|' + po2[0].portfolioSummary);

// Test 2.6: GoalPlanningAction — Patel family
Long t8 = System.currentTimeMillis();
GoalPlanningAction.GoalInput gi1 = new GoalPlanningAction.GoalInput();
gi1.clientName = 'Patel';
List<GoalPlanningAction.GoalOutput> go1 = GoalPlanningAction.getFinancialGoals(new List<GoalPlanningAction.GoalInput>{gi1});
Long d8 = System.currentTimeMillis() - t8;
Boolean p8 = go1[0].goalsSummary != null && go1[0].goalsSummary.contains('Retirement');
System.debug('TEST_2.6|GoalPlanningAction|goal_planning|Patel|' + d8 + 'ms|' + (p8 ? 'PASS' : 'FAIL') + '|' + go1[0].goalsSummary);

// Test 2.7: GoalPlanningAction — Carlos Martinez
Long t9 = System.currentTimeMillis();
GoalPlanningAction.GoalInput gi2 = new GoalPlanningAction.GoalInput();
gi2.clientName = 'Carlos Martinez';
List<GoalPlanningAction.GoalOutput> go2 = GoalPlanningAction.getFinancialGoals(new List<GoalPlanningAction.GoalInput>{gi2});
Long d9 = System.currentTimeMillis() - t9;
Boolean p9 = go2[0].goalsSummary != null && go2[0].goalsSummary.contains('Vacation');
System.debug('TEST_2.7|GoalPlanningAction|goal_planning|Carlos Martinez|' + d9 + 'ms|' + (p9 ? 'PASS' : 'FAIL') + '|' + go2[0].goalsSummary);

// Test 2.8: MeetingPrepAction — Carlos
Long t10 = System.currentTimeMillis();
MeetingPrepAction.PrepInput mi1 = new MeetingPrepAction.PrepInput();
mi1.clientName = 'Carlos';
List<MeetingPrepAction.PrepOutput> mo1 = MeetingPrepAction.getMeetingPrep(new List<MeetingPrepAction.PrepInput>{mi1});
Long d10 = System.currentTimeMillis() - t10;
Boolean p10 = mo1[0].meetingBrief != null && mo1[0].meetingBrief.contains('Retirement Planning');
System.debug('TEST_2.8|MeetingPrepAction|meeting_prep|Carlos|' + d10 + 'ms|' + (p10 ? 'PASS' : 'FAIL') + '|' + mo1[0].meetingBrief);

// Test 2.9: MeetingPrepAction — Sarah Johnson
Long t11 = System.currentTimeMillis();
MeetingPrepAction.PrepInput mi2 = new MeetingPrepAction.PrepInput();
mi2.clientName = 'Sarah Johnson';
List<MeetingPrepAction.PrepOutput> mo2 = MeetingPrepAction.getMeetingPrep(new List<MeetingPrepAction.PrepInput>{mi2});
Long d11 = System.currentTimeMillis() - t11;
Boolean p11 = mo2[0].meetingBrief != null && mo2[0].meetingBrief.contains('Annual Portfolio Review');
System.debug('TEST_2.9|MeetingPrepAction|meeting_prep|Sarah Johnson|' + d11 + 'ms|' + (p11 ? 'PASS' : 'FAIL') + '|' + mo2[0].meetingBrief);

Long totalTime = System.currentTimeMillis() - startTime;
System.debug('========== TOTAL TIME: ' + totalTime + 'ms ==========');
