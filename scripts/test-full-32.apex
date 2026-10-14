// 32-Query Full Test Suite — matches deployment-status.md test matrix
// Tests Q1-Q26 and Q31-Q32 via Apex (Q27-Q30 are agent-level escalation/off-topic)
// Run: sf apex run --file scripts/test-full-32.apex --target-org new-org

Integer p = 0; Integer f = 0;

// Q1: Tell me about the Johnson household
DC_ClientLookupAction.LookupInput i1 = new DC_ClientLookupAction.LookupInput(); i1.clientName = 'Johnson';
String r1 = DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{i1})[0].clientSummary;
Boolean b1 = r1 != null && r1.contains('Johnson'); if(b1){p++;}else{f++;} System.debug('Q01|client_lookup|Johnson|'+(b1?'PASS':'FAIL')+'|'+r1);

// Q2: Tell me about the Chen family
DC_ClientLookupAction.LookupInput i2 = new DC_ClientLookupAction.LookupInput(); i2.clientName = 'Chen';
String r2 = DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{i2})[0].clientSummary;
Boolean b2 = r2 != null && r2.contains('Chen'); if(b2){p++;}else{f++;} System.debug('Q02|client_lookup|Chen|'+(b2?'PASS':'FAIL')+'|'+r2);

// Q3: Tell me about the Martinez household
DC_ClientLookupAction.LookupInput i3 = new DC_ClientLookupAction.LookupInput(); i3.clientName = 'Martinez';
String r3 = DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{i3})[0].clientSummary;
Boolean b3 = r3 != null && r3.contains('Martinez'); if(b3){p++;}else{f++;} System.debug('Q03|client_lookup|Martinez|'+(b3?'PASS':'FAIL')+'|'+r3);

// Q4: Tell me about the Patel family
DC_ClientLookupAction.LookupInput i4 = new DC_ClientLookupAction.LookupInput(); i4.clientName = 'Patel';
String r4 = DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{i4})[0].clientSummary;
Boolean b4 = r4 != null && r4.contains('Patel'); if(b4){p++;}else{f++;} System.debug('Q04|client_lookup|Patel|'+(b4?'PASS':'FAIL')+'|'+r4);

// Q5: Tell me about the Williams family
DC_ClientLookupAction.LookupInput i5 = new DC_ClientLookupAction.LookupInput(); i5.clientName = 'Williams';
String r5 = DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{i5})[0].clientSummary;
Boolean b5 = r5 != null && r5.contains('Williams'); if(b5){p++;}else{f++;} System.debug('Q05|client_lookup|Williams|'+(b5?'PASS':'FAIL')+'|'+r5);

// Q6: How is Wei Chen's portfolio?
DC_PortfolioReviewAction.ReviewInput i6 = new DC_PortfolioReviewAction.ReviewInput(); i6.clientName = 'Wei Chen';
String r6 = DC_PortfolioReviewAction.getPortfolioSummary(new List<DC_PortfolioReviewAction.ReviewInput>{i6})[0].portfolioSummary;
Boolean b6 = r6 != null && r6.contains('Chen'); if(b6){p++;}else{f++;} System.debug('Q06|portfolio_review|Wei Chen|'+(b6?'PASS':'FAIL')+'|'+r6);

// Q7: How is Raj Patel's portfolio performing?
DC_PortfolioReviewAction.ReviewInput i7 = new DC_PortfolioReviewAction.ReviewInput(); i7.clientName = 'Raj Patel';
String r7 = DC_PortfolioReviewAction.getPortfolioSummary(new List<DC_PortfolioReviewAction.ReviewInput>{i7})[0].portfolioSummary;
Boolean b7 = r7 != null && r7.contains('Patel'); if(b7){p++;}else{f++;} System.debug('Q07|portfolio_review|Raj Patel|'+(b7?'PASS':'FAIL')+'|'+r7);

// Q8: Show me James Williams portfolio
DC_PortfolioReviewAction.ReviewInput i8 = new DC_PortfolioReviewAction.ReviewInput(); i8.clientName = 'James Williams';
String r8 = DC_PortfolioReviewAction.getPortfolioSummary(new List<DC_PortfolioReviewAction.ReviewInput>{i8})[0].portfolioSummary;
Boolean b8 = r8 != null && r8.contains('Williams'); if(b8){p++;}else{f++;} System.debug('Q08|portfolio_review|James Williams|'+(b8?'PASS':'FAIL')+'|'+r8);
