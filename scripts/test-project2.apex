// Test all 4 Apex actions for Project 2

// 1. Client Lookup - "Tell me about the Johnsons"
ClientLookupAction.LookupInput ci = new ClientLookupAction.LookupInput();
ci.clientName = 'Johnson';
List<ClientLookupAction.LookupOutput> co = ClientLookupAction.getClient360(new List<ClientLookupAction.LookupInput>{ci});
System.debug('=== CLIENT LOOKUP ===');
System.debug(co[0].clientSummary);

// 2. Portfolio Review - "How is Wei Chen's portfolio?"
PortfolioReviewAction.ReviewInput pi = new PortfolioReviewAction.ReviewInput();
pi.clientName = 'Wei Chen';
List<PortfolioReviewAction.ReviewOutput> po = PortfolioReviewAction.getPortfolioSummary(new List<PortfolioReviewAction.ReviewInput>{pi});
System.debug('=== PORTFOLIO REVIEW ===');
System.debug(po[0].portfolioSummary);

// 3. Goal Planning - "What are the Patels' goals?"
GoalPlanningAction.GoalInput gi = new GoalPlanningAction.GoalInput();
gi.clientName = 'Patel';
List<GoalPlanningAction.GoalOutput> go2 = GoalPlanningAction.getFinancialGoals(new List<GoalPlanningAction.GoalInput>{gi});
System.debug('=== GOAL PLANNING ===');
System.debug(go2[0].goalsSummary);

// 4. Meeting Prep - "Prep me for my meeting with Carlos"
MeetingPrepAction.PrepInput mi = new MeetingPrepAction.PrepInput();
mi.clientName = 'Carlos';
List<MeetingPrepAction.PrepOutput> mo = MeetingPrepAction.getMeetingPrep(new List<MeetingPrepAction.PrepInput>{mi});
System.debug('=== MEETING PREP ===');
System.debug(mo[0].meetingBrief);
