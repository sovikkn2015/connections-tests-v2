// ============================================================================
// Seed Data Part 2 of 3 — IR_Coverage__c, IR_Watchlist__c, IR_Research_Note__c
// Run with: sf apex run --file scripts/apex/seed-02-coverage-watchlist-notes.apex
// Requires: seed-01-accounts-companies.apex to have been run first.
// ============================================================================

try {

// Look up company IDs by ticker
Map<String, Id> companyIds = new Map<String, Id>();
for (IR_Company__c c : [SELECT Id, Ticker__c FROM IR_Company__c]) {
    companyIds.put(c.Ticker__c, c.Id);
}
System.debug('Loaded ' + companyIds.size() + ' company IDs by ticker.');

// === 4. IR_COVERAGE__c (30) — 3 analysts covering 10 stocks each ===
System.debug('=== Creating 30 IR_Coverage__c records ===');

List<IR_Coverage__c> allCoverages = new List<IR_Coverage__c>{
    // Sarah Chen — Tech (10 stocks)
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('NVDA'), Rating__c='Buy', Target_Price__c=1050.00, Last_Updated__c=Date.newInstance(2026,4,1)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('AAPL'), Rating__c='Buy', Target_Price__c=245.00, Last_Updated__c=Date.newInstance(2026,3,28)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('MSFT'), Rating__c='Buy', Target_Price__c=520.00, Last_Updated__c=Date.newInstance(2026,3,25)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('GOOGL'), Rating__c='Hold', Target_Price__c=185.00, Last_Updated__c=Date.newInstance(2026,3,20)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('AMZN'), Rating__c='Hold', Target_Price__c=210.00, Last_Updated__c=Date.newInstance(2026,4,3)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('AMD'), Rating__c='Overweight', Target_Price__c=195.00, Last_Updated__c=Date.newInstance(2026,3,18)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('TSLA'), Rating__c='Underweight', Target_Price__c=180.00, Last_Updated__c=Date.newInstance(2026,4,5)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('CRM'), Rating__c='Overweight', Target_Price__c=340.00, Last_Updated__c=Date.newInstance(2026,3,22)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('META'), Rating__c='Buy', Target_Price__c=620.00, Last_Updated__c=Date.newInstance(2026,3,30)),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=companyIds.get('AVGO'), Rating__c='Buy', Target_Price__c=1400.00, Last_Updated__c=Date.newInstance(2026,4,2)),

    // James Rodriguez — Healthcare + Financials (10 stocks)
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('LLY'), Rating__c='Buy', Target_Price__c=950.00, Last_Updated__c=Date.newInstance(2026,4,4)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('UNH'), Rating__c='Overweight', Target_Price__c=620.00, Last_Updated__c=Date.newInstance(2026,3,27)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('JNJ'), Rating__c='Hold', Target_Price__c=170.00, Last_Updated__c=Date.newInstance(2026,3,15)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('PFE'), Rating__c='Underweight', Target_Price__c=26.00, Last_Updated__c=Date.newInstance(2026,3,19)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('ABBV'), Rating__c='Buy', Target_Price__c=210.00, Last_Updated__c=Date.newInstance(2026,4,1)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('JPM'), Rating__c='Buy', Target_Price__c=250.00, Last_Updated__c=Date.newInstance(2026,3,29)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('BAC'), Rating__c='Overweight', Target_Price__c=48.00, Last_Updated__c=Date.newInstance(2026,3,26)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('WFC'), Rating__c='Hold', Target_Price__c=62.00, Last_Updated__c=Date.newInstance(2026,3,21)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('GS'), Rating__c='Overweight', Target_Price__c=520.00, Last_Updated__c=Date.newInstance(2026,4,3)),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=companyIds.get('MS'), Rating__c='Buy', Target_Price__c=115.00, Last_Updated__c=Date.newInstance(2026,3,24)),

    // Priya Sharma — Energy + Consumer + Industrials + Communication (10 stocks)
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('XOM'), Rating__c='Overweight', Target_Price__c=130.00, Last_Updated__c=Date.newInstance(2026,4,2)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('CVX'), Rating__c='Buy', Target_Price__c=175.00, Last_Updated__c=Date.newInstance(2026,3,28)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('COP'), Rating__c='Hold', Target_Price__c=120.00, Last_Updated__c=Date.newInstance(2026,3,20)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('COST'), Rating__c='Buy', Target_Price__c=950.00, Last_Updated__c=Date.newInstance(2026,4,4)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('WMT'), Rating__c='Overweight', Target_Price__c=85.00, Last_Updated__c=Date.newInstance(2026,3,25)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('HD'), Rating__c='Hold', Target_Price__c=390.00, Last_Updated__c=Date.newInstance(2026,3,18)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('CAT'), Rating__c='Buy', Target_Price__c=410.00, Last_Updated__c=Date.newInstance(2026,4,1)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('HON'), Rating__c='Overweight', Target_Price__c=230.00, Last_Updated__c=Date.newInstance(2026,3,22)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('NFLX'), Rating__c='Buy', Target_Price__c=780.00, Last_Updated__c=Date.newInstance(2026,3,30)),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=companyIds.get('DIS'), Rating__c='Hold', Target_Price__c=120.00, Last_Updated__c=Date.newInstance(2026,3,17))
};
insert allCoverages;
System.debug('Inserted ' + allCoverages.size() + ' IR_Coverage__c records.');


// === 5. IR_WATCHLIST__c (20) — Stocks with upcoming earnings ===
System.debug('=== Creating 20 IR_Watchlist__c records ===');

List<IR_Watchlist__c> allWatchlists = new List<IR_Watchlist__c>{
    new IR_Watchlist__c(Company__c=companyIds.get('NVDA'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,1), Reason__c='AI capex cycle inflection — data center guidance critical'),
    new IR_Watchlist__c(Company__c=companyIds.get('AAPL'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,5), Reason__c='Services revenue trajectory and China iPhone demand'),
    new IR_Watchlist__c(Company__c=companyIds.get('MSFT'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,1), Reason__c='Azure growth rate and Copilot monetization update'),
    new IR_Watchlist__c(Company__c=companyIds.get('GOOGL'), Priority__c='Medium', Added_Date__c=Date.newInstance(2026,3,10), Reason__c='Search AI integration impact on ad revenue'),
    new IR_Watchlist__c(Company__c=companyIds.get('AMZN'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,3), Reason__c='AWS re-acceleration and retail margin expansion'),
    new IR_Watchlist__c(Company__c=companyIds.get('TSLA'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,8), Reason__c='Delivery numbers and FSD regulatory progress'),
    new IR_Watchlist__c(Company__c=companyIds.get('META'), Priority__c='Medium', Added_Date__c=Date.newInstance(2026,3,12), Reason__c='Reality Labs losses and Reels monetization'),
    new IR_Watchlist__c(Company__c=companyIds.get('LLY'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,2), Reason__c='Mounjaro/Zepbound supply ramp and new indication data'),
    new IR_Watchlist__c(Company__c=companyIds.get('JPM'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,1), Reason__c='NII guidance and credit quality trends — bellwether'),
    new IR_Watchlist__c(Company__c=companyIds.get('XOM'), Priority__c='Medium', Added_Date__c=Date.newInstance(2026,3,15), Reason__c='Pioneer integration synergies and Permian production'),
    new IR_Watchlist__c(Company__c=companyIds.get('AVGO'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,7), Reason__c='Custom AI chip orders and VMware cross-sell'),
    new IR_Watchlist__c(Company__c=companyIds.get('COST'), Priority__c='Medium', Added_Date__c=Date.newInstance(2026,3,20), Reason__c='Membership fee increase impact and comp sales'),
    new IR_Watchlist__c(Company__c=companyIds.get('GS'), Priority__c='Medium', Added_Date__c=Date.newInstance(2026,3,10), Reason__c='Trading revenue and asset management AUM growth'),
    new IR_Watchlist__c(Company__c=companyIds.get('UNH'), Priority__c='Medium', Added_Date__c=Date.newInstance(2026,3,14), Reason__c='Medical cost ratio trends and Optum growth'),
    new IR_Watchlist__c(Company__c=companyIds.get('NFLX'), Priority__c='Medium', Added_Date__c=Date.newInstance(2026,3,18), Reason__c='Ad tier subscriber growth and live events strategy'),
    new IR_Watchlist__c(Company__c=companyIds.get('CAT'), Priority__c='Low', Added_Date__c=Date.newInstance(2026,3,22), Reason__c='Infrastructure spending cycle and dealer inventory'),
    new IR_Watchlist__c(Company__c=companyIds.get('PFE'), Priority__c='Low', Added_Date__c=Date.newInstance(2026,3,25), Reason__c='Oncology pipeline progress post-Seagen'),
    new IR_Watchlist__c(Company__c=companyIds.get('AMD'), Priority__c='High', Added_Date__c=Date.newInstance(2026,3,4), Reason__c='MI300X revenue ramp vs NVDA competitive positioning'),
    new IR_Watchlist__c(Company__c=companyIds.get('CRM'), Priority__c='Low', Added_Date__c=Date.newInstance(2026,3,28), Reason__c='Agentforce adoption metrics and margin trajectory'),
    new IR_Watchlist__c(Company__c=companyIds.get('WMT'), Priority__c='Low', Added_Date__c=Date.newInstance(2026,3,30), Reason__c='Walmart+ growth and advertising revenue scale')
};
insert allWatchlists;
System.debug('Inserted ' + allWatchlists.size() + ' IR_Watchlist__c records.');


// === 6. IR_RESEARCH_NOTE__c (5) — Published research briefs ===
System.debug('=== Creating 5 IR_Research_Note__c records ===');

List<IR_Research_Note__c> allNotes = new List<IR_Research_Note__c>{
    new IR_Research_Note__c(
        Company__c=companyIds.get('NVDA'),
        Ticker__c='NVDA',
        Analyst__c='Sarah Chen',
        Rating__c='Buy',
        Target_Price__c=1050.00,
        Generated_Date__c=DateTime.newInstance(2026,3,15,9,0,0),
        Summary__c='NVIDIA continues to dominate the AI accelerator market with its H100 and upcoming B200 GPU architectures. Data center revenue grew 265% year-over-year in the most recent quarter, driven by hyperscaler demand for AI training and inference workloads. Management guided for continued sequential growth as supply constraints ease.\n\nThe competitive moat remains wide due to CUDA ecosystem lock-in, with over 4 million developers building on the platform. AMD MI300X is gaining some traction but remains a distant second in enterprise adoption. Custom silicon from hyperscalers addresses only a fraction of the total addressable market.\n\nWe reiterate our Buy rating with a $1,050 price target based on 35x forward earnings. Key risks include potential demand normalization post-training buildout, export restrictions to China, and customer concentration among top-5 hyperscalers.',
        Full_Brief__c='NVIDIA Corporation (NVDA) — Investment Research Brief Q1 2026\n\nExecutive Summary: NVIDIA continues to dominate the AI accelerator market with its H100 and upcoming B200 GPU architectures. Data center revenue grew 265% YoY, driven by hyperscaler demand for AI training and inference workloads. Management guided for continued sequential growth as supply constraints ease.\n\nCompetitive Position: The competitive moat remains wide due to CUDA ecosystem lock-in, with over 4 million developers on the platform. AMD MI300X is gaining traction but remains a distant second in enterprise adoption. Custom silicon from hyperscalers addresses only a fraction of the TAM.\n\nValuation: We reiterate our Buy rating with a $1,050 price target based on 35x forward earnings.\n\nInvestment Thesis: AI infrastructure spending is a multi-year secular trend. NVIDIA captures the largest share of GPU compute spend with unmatched software ecosystem advantages.\n\nCatalysts: B200 production ramp in Q2 2026; Sovereign AI deals expanding TAM; Inference workload growth as AI applications scale; Networking revenue from Spectrum-X platform.\n\nRisks: China export restrictions tightening; Customer concentration risk with top-5 hyperscalers representing 50%+ of revenue; Potential demand air pocket post-training infrastructure buildout; Custom silicon competition.'
    ),
    new IR_Research_Note__c(
        Company__c=companyIds.get('AAPL'),
        Ticker__c='AAPL',
        Analyst__c='Sarah Chen',
        Rating__c='Buy',
        Target_Price__c=245.00,
        Generated_Date__c=DateTime.newInstance(2026,3,18,10,30,0),
        Summary__c='Apple reported solid Q1 results with Services revenue reaching a new all-time high of $26.3B, growing 14% year-over-year. The installed base of active devices exceeded 2.3 billion, providing a durable foundation for recurring services monetization. iPhone revenue was roughly flat as the upgrade cycle for iPhone 17 builds anticipation.\n\nApple Intelligence features are driving measurable increases in device engagement and creating new monetization vectors through premium AI capabilities. The Vision Pro spatial computing platform is finding traction in enterprise use cases, though consumer adoption remains nascent.\n\nWe upgrade to Buy from Hold with a $245 price target. The services business alone justifies a significant portion of the current market cap, and we see iPhone 17 as a meaningful upgrade catalyst with on-device AI capabilities.',
        Full_Brief__c='Apple Inc. (AAPL) — Investment Research Brief Q1 2026\n\nExecutive Summary: Apple reported solid Q1 results with Services revenue reaching a new all-time high of $26.3B, growing 14% YoY. The installed base of active devices exceeded 2.3 billion, providing a durable foundation for recurring services monetization.\n\nAI Strategy: Apple Intelligence features are driving measurable increases in device engagement and creating new monetization vectors through premium AI capabilities. Vision Pro is finding traction in enterprise use cases.\n\nValuation: We upgrade to Buy from Hold with a $245 price target. The services business alone justifies a significant portion of the current market cap.\n\nInvestment Thesis: Services revenue growth and margin expansion, combined with the iPhone 17 AI-driven upgrade cycle, support premium valuation. Installed base monetization is underappreciated.\n\nCatalysts: iPhone 17 launch with enhanced Apple Intelligence; Services revenue crossing $30B quarterly run rate; India manufacturing expansion; Vision Pro enterprise adoption.\n\nRisks: China regulatory and competitive headwinds; Smartphone market saturation in developed markets; App Store regulatory pressure in EU and US; Vision Pro consumer adoption slower than expected.'
    ),
    new IR_Research_Note__c(
        Company__c=companyIds.get('JPM'),
        Ticker__c='JPM',
        Analyst__c='James Rodriguez',
        Rating__c='Buy',
        Target_Price__c=250.00,
        Generated_Date__c=DateTime.newInstance(2026,3,20,8,0,0),
        Summary__c='JPMorgan Chase delivered another strong quarter with record net revenue of $44.2B. Net interest income remained robust at $24.1B despite the rate cut cycle, as loan growth and deposit repricing offset lower benchmark rates. The investment banking franchise captured market share with fees up 32% year-over-year.\n\nCredit quality remains benign with net charge-offs at 62bps, below the through-cycle average. Management built reserves modestly, signaling confidence in the economic outlook. The CIB division continues to benefit from elevated M&A and IPO activity as the capital markets cycle recovers.\n\nWe maintain our Buy rating with a $250 price target. JPM trades at 2.1x tangible book value, justified given its consistent 17%+ ROTCE and dominant competitive position across all major banking verticals.',
        Full_Brief__c='JPMorgan Chase & Co. (JPM) — Investment Research Brief Q1 2026\n\nExecutive Summary: JPMorgan Chase delivered another strong quarter with record net revenue of $44.2B. Net interest income remained robust at $24.1B despite the rate cut cycle.\n\nInvestment Banking: The IB franchise captured market share with fees up 32% YoY. The CIB division continues to benefit from elevated M&A and IPO activity.\n\nCredit Quality: Net charge-offs at 62bps, below the through-cycle average. Management built reserves modestly, signaling confidence.\n\nValuation: We maintain our Buy rating with a $250 price target. JPM trades at 2.1x tangible book value, justified given its consistent 17%+ ROTCE.\n\nInvestment Thesis: Best-in-class universal bank with dominant market positions across consumer, commercial, and investment banking.\n\nCatalysts: Capital markets recovery driving IB fees; Credit card loan growth; International expansion in UK digital banking; Increased capital return as Basel III endgame clarity emerges.\n\nRisks: Credit cycle deterioration in consumer lending; NII pressure from accelerated rate cuts; Regulatory capital requirements under Basel III endgame.'
    ),
    new IR_Research_Note__c(
        Company__c=companyIds.get('LLY'),
        Ticker__c='LLY',
        Analyst__c='James Rodriguez',
        Rating__c='Buy',
        Target_Price__c=950.00,
        Generated_Date__c=DateTime.newInstance(2026,3,22,11,0,0),
        Summary__c='Eli Lilly reported exceptional results driven by the GLP-1 franchise. Mounjaro revenue reached $4.5B in the quarter while Zepbound obesity sales hit $1.8B, both exceeding consensus estimates. Supply constraints are easing as new manufacturing capacity comes online, with management guiding for significant sequential improvement in product availability.\n\nThe pipeline continues to deliver with orforglipron (oral GLP-1) showing promising Phase 3 data that could dramatically expand the addressable market. Retatrutide (triple agonist) Phase 3 results expected in H2 2026 represent the next major catalyst.\n\nWe reiterate Buy with a $950 price target. The obesity market alone could reach $100B+ by 2030, and Lilly is positioned to capture the largest share. Current valuation is demanding at 55x forward earnings but justified by the growth trajectory.',
        Full_Brief__c='Eli Lilly and Company (LLY) — Investment Research Brief Q1 2026\n\nExecutive Summary: Eli Lilly reported exceptional results driven by the GLP-1 franchise. Mounjaro revenue reached $4.5B while Zepbound obesity sales hit $1.8B, both exceeding consensus.\n\nSupply & Manufacturing: Supply constraints are easing as new manufacturing capacity comes online.\n\nPipeline: Orforglipron (oral GLP-1) showing promising Phase 3 data. Retatrutide (triple agonist) Phase 3 results expected in H2 2026.\n\nValuation: We reiterate Buy with a $950 price target. The obesity market alone could reach $100B+ by 2030.\n\nInvestment Thesis: GLP-1 franchise in obesity and diabetes represents a generational pharmaceutical opportunity.\n\nCatalysts: Orforglipron Phase 3 readout; Zepbound supply normalization; New obesity indications; International launches.\n\nRisks: GLP-1 competition from Novo Nordisk; Manufacturing scale-up execution; Pricing pressure from IRA negotiation.'
    ),
    new IR_Research_Note__c(
        Company__c=companyIds.get('XOM'),
        Ticker__c='XOM',
        Analyst__c='Priya Sharma',
        Rating__c='Overweight',
        Target_Price__c=130.00,
        Generated_Date__c=DateTime.newInstance(2026,3,25,14,0,0),
        Summary__c='ExxonMobil reported solid results with upstream production reaching 4.2M barrels of oil equivalent per day following the Pioneer Natural Resources integration. Permian Basin production is on track to reach 2.3M boepd by 2027, making Exxon the largest producer in the basin. Cost synergies from the Pioneer deal are running ahead of the $2B annual target.\n\nThe downstream and chemical segments benefited from improved refining margins and polyethylene demand recovery. Low Carbon Solutions is progressing with the Baytown CCS hub and lithium extraction projects, though these remain pre-revenue.\n\nWe maintain Overweight with a $130 price target. At current oil prices, Exxon generates substantial free cash flow supporting the dividend and $20B annual buyback program. The Pioneer integration provides visible production growth through decade-end.',
        Full_Brief__c='Exxon Mobil Corporation (XOM) — Investment Research Brief Q1 2026\n\nExecutive Summary: ExxonMobil reported solid results with upstream production reaching 4.2M boepd following the Pioneer Natural Resources integration. Permian Basin production on track to reach 2.3M boepd by 2027.\n\nPioneer Integration: Cost synergies running ahead of the $2B annual target. Exxon is now the largest Permian Basin producer.\n\nDownstream & Chemical: Benefited from improved refining margins and polyethylene demand recovery.\n\nLow Carbon Solutions: Baytown CCS hub and lithium extraction projects progressing, though pre-revenue.\n\nValuation: We maintain Overweight with a $130 price target. Substantial free cash flow supports the dividend and $20B annual buyback.\n\nInvestment Thesis: Pioneer integration creates the premier Permian Basin position with visible production growth and cost synergies.\n\nCatalysts: Pioneer synergy realization ahead of schedule; Permian production milestones; Guyana Phase 3+ developments; Potential for special dividends.\n\nRisks: Oil price decline below $60/bbl; Energy transition policy risk; Pioneer integration execution; Permian Basin infrastructure constraints.'
    )
};
insert allNotes;
System.debug('Inserted ' + allNotes.size() + ' IR_Research_Note__c records.');

// === SUMMARY ===
System.debug('============================================');
System.debug('=== SEED PART 2 COMPLETE ===');
System.debug('  IR_Coverage__c:    ' + allCoverages.size());
System.debug('  IR_Watchlist__c:   ' + allWatchlists.size());
System.debug('  IR_Research_Note:  ' + allNotes.size());
System.debug('============================================');

} catch (Exception e) {
    System.debug(LoggingLevel.ERROR, '=== SEED PART 2 ERROR ===');
    System.debug(LoggingLevel.ERROR, 'Message: ' + e.getMessage());
    System.debug(LoggingLevel.ERROR, 'Type: ' + e.getTypeName());
    System.debug(LoggingLevel.ERROR, 'Stack: ' + e.getStackTraceString());
    throw e;
}
