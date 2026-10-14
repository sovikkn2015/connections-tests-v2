// ============================================================================
// ⚠️  THIS FILE IS TOO LARGE FOR ANONYMOUS APEX EXECUTION.
// Use the split scripts instead:
//   sf apex run --file scripts/apex/seed-01-accounts-companies.apex --target-org my-org
//   sf apex run --file scripts/apex/seed-02-coverage-watchlist-notes.apex --target-org my-org
//   sf apex run --file scripts/apex/seed-03-audit-logs.apex --target-org my-org
// ============================================================================
// Seed Data for Project 006 — OpenClaw FSI IR Platform (REFERENCE COPY)
// Run with: sf apex run --file scripts/apex/seed-data.apex
// Idempotent: deletes existing IR_* records before inserting fresh data.
// ============================================================================

try {

// === CLEAN SLATE — delete Accounts/Contacts and IR_* records ===
System.debug('=== Deleting existing test Accounts, Contacts, and IR_* records ===');

// Delete existing test accounts (only those created by this script)
List<String> testAccountNames = new List<String>{
    'Henderson Family', 'Nakamura Trust', 'Reeves Retirement', 'Patel Holdings',
    'Morrison Capital', 'O\'Connell Estate', 'Zhang Family Trust', 'Kowalski Wealth',
    'DuBois Legacy Fund', 'Singh Growth Portfolio', 'Blackwood Family Office',
    'Ashford & Partners FO', 'Meridian Family Office', 'Sterling House FO',
    'Pacifica Family Office', 'Great Lakes Pension Fund', 'Sunbelt Endowment',
    'Cascade Insurance Group', 'Midwest Foundation Trust', 'Harbor Re Insurance',
    'TechBridge Ventures', 'Irongate Capital Corp', 'Blue Ridge Holdings',
    'Summit Corporate Treasury', 'Bayshore Capital Group'
};
delete [SELECT Id FROM Contact WHERE Account.Name IN :testAccountNames];
delete [SELECT Id FROM Account WHERE Name IN :testAccountNames];

// Delete IR_* records (child → parent order)
delete [SELECT Id FROM IR_Audit_Log__c];
delete [SELECT Id FROM IR_Research_Note__c];
delete [SELECT Id FROM IR_Watchlist__c];
delete [SELECT Id FROM IR_Coverage__c];
delete [SELECT Id FROM IR_Company__c];
System.debug('Existing records deleted.');

// === 1. CLIENT ACCOUNTS (25) ===
System.debug('=== Creating 25 Client Accounts ===');

// 10 HNW Individuals
Account henderson = new Account(Name='Henderson Family', BillingCity='Greenwich', BillingState='CT', Industry='Financial Services');
Account nakamura = new Account(Name='Nakamura Trust', BillingCity='San Francisco', BillingState='CA', Industry='Financial Services');
Account reeves = new Account(Name='Reeves Retirement', BillingCity='Scottsdale', BillingState='AZ', Industry='Financial Services');
Account patel = new Account(Name='Patel Holdings', BillingCity='Houston', BillingState='TX', Industry='Financial Services');
Account morrison = new Account(Name='Morrison Capital', BillingCity='Chicago', BillingState='IL', Industry='Financial Services');
Account oconnell = new Account(Name='O\'Connell Estate', BillingCity='Boston', BillingState='MA', Industry='Financial Services');
Account zhang = new Account(Name='Zhang Family Trust', BillingCity='Seattle', BillingState='WA', Industry='Financial Services');
Account kowalski = new Account(Name='Kowalski Wealth', BillingCity='Denver', BillingState='CO', Industry='Financial Services');
Account dubois = new Account(Name='DuBois Legacy Fund', BillingCity='New Orleans', BillingState='LA', Industry='Financial Services');
Account singh = new Account(Name='Singh Growth Portfolio', BillingCity='Austin', BillingState='TX', Industry='Financial Services');

// 5 Family Offices
Account blackwood = new Account(Name='Blackwood Family Office', BillingCity='New York', BillingState='NY', Industry='Financial Services');
Account ashford = new Account(Name='Ashford & Partners FO', BillingCity='Palm Beach', BillingState='FL', Industry='Financial Services');
Account meridian = new Account(Name='Meridian Family Office', BillingCity='Dallas', BillingState='TX', Industry='Financial Services');
Account sterling = new Account(Name='Sterling House FO', BillingCity='Philadelphia', BillingState='PA', Industry='Financial Services');
Account pacifica = new Account(Name='Pacifica Family Office', BillingCity='Los Angeles', BillingState='CA', Industry='Financial Services');

// 5 Institutional Investors
Account greatLakes = new Account(Name='Great Lakes Pension Fund', BillingCity='Detroit', BillingState='MI', Industry='Financial Services');
Account sunbelt = new Account(Name='Sunbelt Endowment', BillingCity='Atlanta', BillingState='GA', Industry='Financial Services');
Account cascadeIns = new Account(Name='Cascade Insurance Group', BillingCity='Portland', BillingState='OR', Industry='Financial Services');
Account midwestFdn = new Account(Name='Midwest Foundation Trust', BillingCity='Minneapolis', BillingState='MN', Industry='Financial Services');
Account harborRe = new Account(Name='Harbor Re Insurance', BillingCity='Hartford', BillingState='CT', Industry='Financial Services');

// 5 Corporate Accounts
Account techbridge = new Account(Name='TechBridge Ventures', BillingCity='San Jose', BillingState='CA', Industry='Financial Services');
Account irongate = new Account(Name='Irongate Capital Corp', BillingCity='Charlotte', BillingState='NC', Industry='Financial Services');
Account blueridge = new Account(Name='Blue Ridge Holdings', BillingCity='Richmond', BillingState='VA', Industry='Financial Services');
Account summitCorp = new Account(Name='Summit Corporate Treasury', BillingCity='Salt Lake City', BillingState='UT', Industry='Financial Services');
Account bayshore = new Account(Name='Bayshore Capital Group', BillingCity='Miami', BillingState='FL', Industry='Financial Services');

List<Account> allAccounts = new List<Account>{
    henderson, nakamura, reeves, patel, morrison, oconnell, zhang, kowalski, dubois, singh,
    blackwood, ashford, meridian, sterling, pacifica,
    greatLakes, sunbelt, cascadeIns, midwestFdn, harborRe,
    techbridge, irongate, blueridge, summitCorp, bayshore
};
insert allAccounts;
System.debug('Inserted ' + allAccounts.size() + ' Accounts.');

// === 2. CONTACTS (40) — 2 per account for first 20 accounts ===
System.debug('=== Creating 40 Contacts ===');

List<Contact> allContacts = new List<Contact>{
    // Henderson Family
    new Contact(FirstName='Robert', LastName='Henderson', AccountId=henderson.Id, Title='Primary Contact', Email='robert.henderson@example.com', Phone='555-101-0001'),
    new Contact(FirstName='Catherine', LastName='Henderson', AccountId=henderson.Id, Title='Spouse', Email='catherine.henderson@example.com', Phone='555-101-0002'),
    // Nakamura Trust
    new Contact(FirstName='Kenji', LastName='Nakamura', AccountId=nakamura.Id, Title='Trustee', Email='kenji.nakamura@example.com', Phone='555-102-0001'),
    new Contact(FirstName='Yuki', LastName='Nakamura', AccountId=nakamura.Id, Title='Beneficiary Contact', Email='yuki.nakamura@example.com', Phone='555-102-0002'),
    // Reeves Retirement
    new Contact(FirstName='William', LastName='Reeves', AccountId=reeves.Id, Title='Primary Contact', Email='william.reeves@example.com', Phone='555-103-0001'),
    new Contact(FirstName='Margaret', LastName='Reeves', AccountId=reeves.Id, Title='Spouse', Email='margaret.reeves@example.com', Phone='555-103-0002'),
    // Patel Holdings
    new Contact(FirstName='Vikram', LastName='Patel', AccountId=patel.Id, Title='Managing Director', Email='vikram.patel@example.com', Phone='555-104-0001'),
    new Contact(FirstName='Anita', LastName='Patel', AccountId=patel.Id, Title='CFO', Email='anita.patel@example.com', Phone='555-104-0002'),
    // Morrison Capital
    new Contact(FirstName='David', LastName='Morrison', AccountId=morrison.Id, Title='Primary Contact', Email='david.morrison@example.com', Phone='555-105-0001'),
    new Contact(FirstName='Laura', LastName='Morrison', AccountId=morrison.Id, Title='Spouse', Email='laura.morrison@example.com', Phone='555-105-0002'),
    // O'Connell Estate
    new Contact(FirstName='Patrick', LastName='O\'Connell', AccountId=oconnell.Id, Title='Trustee', Email='patrick.oconnell@example.com', Phone='555-106-0001'),
    new Contact(FirstName='Siobhan', LastName='O\'Connell', AccountId=oconnell.Id, Title='Beneficiary Contact', Email='siobhan.oconnell@example.com', Phone='555-106-0002'),
    // Zhang Family Trust
    new Contact(FirstName='Wei', LastName='Zhang', AccountId=zhang.Id, Title='Primary Contact', Email='wei.zhang@example.com', Phone='555-107-0001'),
    new Contact(FirstName='Mei', LastName='Zhang', AccountId=zhang.Id, Title='Spouse', Email='mei.zhang@example.com', Phone='555-107-0002'),
    // Kowalski Wealth
    new Contact(FirstName='Stefan', LastName='Kowalski', AccountId=kowalski.Id, Title='Primary Contact', Email='stefan.kowalski@example.com', Phone='555-108-0001'),
    new Contact(FirstName='Anna', LastName='Kowalski', AccountId=kowalski.Id, Title='Spouse', Email='anna.kowalski@example.com', Phone='555-108-0002'),
    // DuBois Legacy Fund
    new Contact(FirstName='Jean-Pierre', LastName='DuBois', AccountId=dubois.Id, Title='Trustee', Email='jean-pierre.dubois@example.com', Phone='555-109-0001'),
    new Contact(FirstName='Colette', LastName='DuBois', AccountId=dubois.Id, Title='Beneficiary Contact', Email='colette.dubois@example.com', Phone='555-109-0002'),
    // Singh Growth Portfolio
    new Contact(FirstName='Arjun', LastName='Singh', AccountId=singh.Id, Title='Primary Contact', Email='arjun.singh@example.com', Phone='555-110-0001'),
    new Contact(FirstName='Priya', LastName='Singh', AccountId=singh.Id, Title='Spouse', Email='priya.singh@example.com', Phone='555-110-0002'),
    // Blackwood Family Office
    new Contact(FirstName='Charles', LastName='Blackwood', AccountId=blackwood.Id, Title='Principal', Email='charles.blackwood@example.com', Phone='555-111-0001'),
    new Contact(FirstName='Eleanor', LastName='Blackwood', AccountId=blackwood.Id, Title='CFO', Email='eleanor.blackwood@example.com', Phone='555-111-0002'),
    // Ashford & Partners FO
    new Contact(FirstName='Richard', LastName='Ashford', AccountId=ashford.Id, Title='Managing Partner', Email='richard.ashford@example.com', Phone='555-112-0001'),
    new Contact(FirstName='Diana', LastName='Ashford', AccountId=ashford.Id, Title='Spouse', Email='diana.ashford@example.com', Phone='555-112-0002'),
    // Meridian Family Office
    new Contact(FirstName='Marcus', LastName='Whitfield', AccountId=meridian.Id, Title='CIO', Email='marcus.whitfield@example.com', Phone='555-113-0001'),
    new Contact(FirstName='Sandra', LastName='Whitfield', AccountId=meridian.Id, Title='Trustee', Email='sandra.whitfield@example.com', Phone='555-113-0002'),
    // Sterling House FO
    new Contact(FirstName='Jonathan', LastName='Sterling', AccountId=sterling.Id, Title='Principal', Email='jonathan.sterling@example.com', Phone='555-114-0001'),
    new Contact(FirstName='Victoria', LastName='Sterling', AccountId=sterling.Id, Title='Spouse', Email='victoria.sterling@example.com', Phone='555-114-0002'),
    // Pacifica Family Office
    new Contact(FirstName='Michael', LastName='Tanaka', AccountId=pacifica.Id, Title='Managing Director', Email='michael.tanaka@example.com', Phone='555-115-0001'),
    new Contact(FirstName='Lisa', LastName='Tanaka', AccountId=pacifica.Id, Title='CFO', Email='lisa.tanaka@example.com', Phone='555-115-0002'),
    // Great Lakes Pension Fund
    new Contact(FirstName='Thomas', LastName='Brennan', AccountId=greatLakes.Id, Title='CIO', Email='thomas.brennan@example.com', Phone='555-116-0001'),
    new Contact(FirstName='Karen', LastName='Okafor', AccountId=greatLakes.Id, Title='Portfolio Manager', Email='karen.okafor@example.com', Phone='555-116-0002'),
    // Sunbelt Endowment
    new Contact(FirstName='James', LastName='Calloway', AccountId=sunbelt.Id, Title='Executive Director', Email='james.calloway@example.com', Phone='555-117-0001'),
    new Contact(FirstName='Maria', LastName='Vasquez', AccountId=sunbelt.Id, Title='CFO', Email='maria.vasquez@example.com', Phone='555-117-0002'),
    // Cascade Insurance Group
    new Contact(FirstName='Brian', LastName='Larsen', AccountId=cascadeIns.Id, Title='CIO', Email='brian.larsen@example.com', Phone='555-118-0001'),
    new Contact(FirstName='Jennifer', LastName='Nguyen', AccountId=cascadeIns.Id, Title='Risk Manager', Email='jennifer.nguyen@example.com', Phone='555-118-0002'),
    // Midwest Foundation Trust
    new Contact(FirstName='Daniel', LastName='Hoffman', AccountId=midwestFdn.Id, Title='Trustee', Email='daniel.hoffman@example.com', Phone='555-119-0001'),
    new Contact(FirstName='Susan', LastName='Ramirez', AccountId=midwestFdn.Id, Title='CFO', Email='susan.ramirez@example.com', Phone='555-119-0002'),
    // Harbor Re Insurance
    new Contact(FirstName='Gregory', LastName='Walsh', AccountId=harborRe.Id, Title='CIO', Email='gregory.walsh@example.com', Phone='555-120-0001'),
    new Contact(FirstName='Rachel', LastName='Kim', AccountId=harborRe.Id, Title='Portfolio Manager', Email='rachel.kim@example.com', Phone='555-120-0002')
};
insert allContacts;
System.debug('Inserted ' + allContacts.size() + ' Contacts.');


// === 3. IR_COMPANY__c (30) — Real companies across sectors ===
System.debug('=== Creating 30 IR_Company__c records ===');

// Technology (10)
IR_Company__c nvda = new IR_Company__c(Name='NVIDIA Corporation', Ticker__c='NVDA', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=3200000000000.0, Description__c='Leading designer of graphics processing units (GPUs) and system-on-chip units. Dominant position in AI/ML training and inference hardware. Data center revenue now exceeds gaming segment.');
IR_Company__c aapl = new IR_Company__c(Name='Apple Inc.', Ticker__c='AAPL', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=2900000000000.0, Description__c='Consumer electronics and services giant. iPhone ecosystem drives recurring services revenue. Expanding into AR/VR with Vision Pro and deepening financial services.');
IR_Company__c msft = new IR_Company__c(Name='Microsoft Corporation', Ticker__c='MSFT', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=3100000000000.0, Description__c='Enterprise software and cloud computing leader. Azure cloud platform is the #2 global provider. Copilot AI integration across Office 365, GitHub, and Dynamics driving new revenue streams.');
IR_Company__c googl = new IR_Company__c(Name='Alphabet Inc.', Ticker__c='GOOGL', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=2100000000000.0, Description__c='Parent company of Google. Dominates digital advertising through Search and YouTube. Google Cloud Platform growing rapidly. Gemini AI models competing in the foundation model space.');
IR_Company__c amzn = new IR_Company__c(Name='Amazon.com Inc.', Ticker__c='AMZN', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=2000000000000.0, Description__c='E-commerce and cloud computing giant. AWS is the #1 global cloud provider. Advertising business is the fastest-growing segment. Expanding AI services through Bedrock and custom chips.');
IR_Company__c amd = new IR_Company__c(Name='Advanced Micro Devices', Ticker__c='AMD', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=280000000000.0, Description__c='Semiconductor company competing in CPUs and GPUs. MI300X AI accelerator gaining data center traction. Server CPU market share growing against Intel.');
IR_Company__c tsla = new IR_Company__c(Name='Tesla Inc.', Ticker__c='TSLA', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=800000000000.0, Description__c='Electric vehicle manufacturer and clean energy company. Full Self-Driving software and Dojo supercomputer represent AI optionality. Energy storage business growing rapidly.');
IR_Company__c crm = new IR_Company__c(Name='Salesforce Inc.', Ticker__c='CRM', Sector__c='Technology', Exchange__c='NYSE', Market_Cap__c=275000000000.0, Description__c='Enterprise CRM platform leader. Agentforce AI agents represent next-generation customer engagement. Data Cloud unifying customer data. Margin expansion through operational discipline.');
IR_Company__c meta = new IR_Company__c(Name='Meta Platforms Inc.', Ticker__c='META', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=1400000000000.0, Description__c='Social media and metaverse company. Facebook, Instagram, and WhatsApp reach billions. Reels competing with TikTok. Reality Labs investing heavily in AR/VR.');
IR_Company__c avgo = new IR_Company__c(Name='Broadcom Inc.', Ticker__c='AVGO', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=750000000000.0, Description__c='Semiconductor and infrastructure software conglomerate. Custom AI accelerators for hyperscalers. VMware acquisition transforming software portfolio. Networking chips critical for AI data centers.');

// Healthcare (5)
IR_Company__c lly = new IR_Company__c(Name='Eli Lilly and Company', Ticker__c='LLY', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=800000000000.0, Description__c='Pharmaceutical company with blockbuster GLP-1 drugs Mounjaro and Zepbound. Obesity and diabetes pipeline is industry-leading. Strong pricing power and expanding indications.');
IR_Company__c unh = new IR_Company__c(Name='UnitedHealth Group', Ticker__c='UNH', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=480000000000.0, Description__c='Largest US health insurer and healthcare services company. Optum health services division drives margin expansion. Medicare Advantage enrollment growing steadily.');
IR_Company__c jnj = new IR_Company__c(Name='Johnson & Johnson', Ticker__c='JNJ', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=380000000000.0, Description__c='Diversified healthcare company post-Kenvue consumer health spinoff. Innovative Medicine segment focused on immunology, oncology, and neuroscience. MedTech in surgical robotics.');
IR_Company__c pfe = new IR_Company__c(Name='Pfizer Inc.', Ticker__c='PFE', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=160000000000.0, Description__c='Global pharmaceutical company navigating post-COVID revenue normalization. Seagen acquisition bolstering oncology pipeline. Cost restructuring program underway.');
IR_Company__c abbv = new IR_Company__c(Name='AbbVie Inc.', Ticker__c='ABBV', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=310000000000.0, Description__c='Biopharmaceutical company managing Humira biosimilar competition. Skyrizi and Rinvoq immunology franchise growing rapidly. Strong free cash flow generation.');

// Financials (5)
IR_Company__c jpm = new IR_Company__c(Name='JPMorgan Chase & Co.', Ticker__c='JPM', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=580000000000.0, Description__c='Largest US bank by assets. Leading positions in investment banking, commercial banking, asset management, and consumer banking. Technology spending exceeds most fintech competitors.');
IR_Company__c bac = new IR_Company__c(Name='Bank of America Corp', Ticker__c='BAC', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=310000000000.0, Description__c='Second-largest US bank. Consumer banking franchise with strong digital adoption. Merrill Lynch wealth management. Net interest income sensitive to rate environment.');
IR_Company__c wfc = new IR_Company__c(Name='Wells Fargo & Company', Ticker__c='WFC', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=200000000000.0, Description__c='Diversified financial services company. Asset cap removal would be a significant catalyst. Efficiency ratio improving under current management. Strong mortgage origination franchise.');
IR_Company__c gs = new IR_Company__c(Name='Goldman Sachs Group', Ticker__c='GS', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=155000000000.0, Description__c='Premier investment bank and asset manager. Platform Solutions segment being restructured. Trading revenue benefits from market volatility. Asset management AUM growing steadily.');
IR_Company__c ms = new IR_Company__c(Name='Morgan Stanley', Ticker__c='MS', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=165000000000.0, Description__c='Global financial services firm with leading wealth management franchise. E*TRADE integration complete. Investment management AUM at record levels. Fee-based revenue model.');

// Energy (3)
IR_Company__c xom = new IR_Company__c(Name='Exxon Mobil Corporation', Ticker__c='XOM', Sector__c='Energy', Exchange__c='NYSE', Market_Cap__c=460000000000.0, Description__c='Largest US integrated oil and gas company. Pioneer Natural Resources acquisition expanding Permian Basin position. Low-carbon solutions investment in CCS and hydrogen.');
IR_Company__c cvx = new IR_Company__c(Name='Chevron Corporation', Ticker__c='CVX', Sector__c='Energy', Exchange__c='NYSE', Market_Cap__c=290000000000.0, Description__c='Integrated energy company with strong upstream portfolio. Permian Basin and Gulf of Mexico production growing. LNG export capacity expanding. Shareholder return program.');
IR_Company__c cop = new IR_Company__c(Name='ConocoPhillips', Ticker__c='COP', Sector__c='Energy', Exchange__c='NYSE', Market_Cap__c=140000000000.0, Description__c='Largest independent E&P company. Low-cost supply advantage in Lower 48. Alaska and international assets provide diversification. Disciplined capital return framework.');

// Consumer (3)
IR_Company__c cost = new IR_Company__c(Name='Costco Wholesale Corp', Ticker__c='COST', Sector__c='Consumer', Exchange__c='NASDAQ', Market_Cap__c=370000000000.0, Description__c='Membership warehouse club operator. Membership renewal rates above 90%. E-commerce growing rapidly. International expansion in Asia and Europe. Kirkland private label brand strength.');
IR_Company__c wmt = new IR_Company__c(Name='Walmart Inc.', Ticker__c='WMT', Sector__c='Consumer', Exchange__c='NYSE', Market_Cap__c=480000000000.0, Description__c='Largest retailer globally. Walmart+ membership growing. Advertising and marketplace businesses expanding margins. Supply chain automation and store remodels driving efficiency.');
IR_Company__c hd = new IR_Company__c(Name='The Home Depot Inc.', Ticker__c='HD', Sector__c='Consumer', Exchange__c='NYSE', Market_Cap__c=360000000000.0, Description__c='Largest home improvement retailer. Pro customer segment is key growth driver. SRS Distribution acquisition expanding addressable market. Housing turnover recovery would be a catalyst.');

// Industrials (2)
IR_Company__c cat = new IR_Company__c(Name='Caterpillar Inc.', Ticker__c='CAT', Sector__c='Industrials', Exchange__c='NYSE', Market_Cap__c=180000000000.0, Description__c='Global leader in construction and mining equipment. Services revenue growing as installed base expands. Infrastructure spending tailwinds from government programs. Strong pricing discipline.');
IR_Company__c hon = new IR_Company__c(Name='Honeywell International', Ticker__c='HON', Sector__c='Industrials', Exchange__c='NYSE', Market_Cap__c=145000000000.0, Description__c='Diversified industrial technology company. Aerospace aftermarket revenue growing. Building automation and energy management. Quantinuum quantum computing subsidiary.');

// Communication Services (2)
IR_Company__c nflx = new IR_Company__c(Name='Netflix Inc.', Ticker__c='NFLX', Sector__c='Communication Services', Exchange__c='NASDAQ', Market_Cap__c=310000000000.0, Description__c='Global streaming entertainment leader. Ad-supported tier driving subscriber growth and new revenue stream. Password sharing crackdown boosting paid memberships. Live events expanding content.');
IR_Company__c dis = new IR_Company__c(Name='The Walt Disney Company', Ticker__c='DIS', Sector__c='Communication Services', Exchange__c='NYSE', Market_Cap__c=200000000000.0, Description__c='Diversified entertainment conglomerate. Disney+ streaming approaching profitability. Parks and experiences segment generating record revenue. ESPN digital transformation underway.');

List<IR_Company__c> allCompanies = new List<IR_Company__c>{
    nvda, aapl, msft, googl, amzn, amd, tsla, crm, meta, avgo,
    lly, unh, jnj, pfe, abbv,
    jpm, bac, wfc, gs, ms,
    xom, cvx, cop,
    cost, wmt, hd,
    cat, hon,
    nflx, dis
};
insert allCompanies;
System.debug('Inserted ' + allCompanies.size() + ' IR_Company__c records.');


// === 4. IR_COVERAGE__c (30) — 3 analysts covering 10 stocks each ===
System.debug('=== Creating 30 IR_Coverage__c records ===');

List<IR_Coverage__c> allCoverages = new List<IR_Coverage__c>{
    // Sarah Chen — Tech (10 stocks)
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=nvda.Id, Rating__c='Buy', Target_Price__c=1050.00, Last_Updated__c=Date.newInstance(2026,4,1), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=aapl.Id, Rating__c='Buy', Target_Price__c=245.00, Last_Updated__c=Date.newInstance(2026,3,28), Last_Action__c='Upgraded'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=msft.Id, Rating__c='Buy', Target_Price__c=520.00, Last_Updated__c=Date.newInstance(2026,3,25), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=googl.Id, Rating__c='Hold', Target_Price__c=185.00, Last_Updated__c=Date.newInstance(2026,3,20), Last_Action__c='Downgraded'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=amzn.Id, Rating__c='Hold', Target_Price__c=210.00, Last_Updated__c=Date.newInstance(2026,4,3), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=amd.Id, Rating__c='Overweight', Target_Price__c=195.00, Last_Updated__c=Date.newInstance(2026,3,18), Last_Action__c='Initiated'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=tsla.Id, Rating__c='Underweight', Target_Price__c=180.00, Last_Updated__c=Date.newInstance(2026,4,5), Last_Action__c='Downgraded'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=crm.Id, Rating__c='Overweight', Target_Price__c=340.00, Last_Updated__c=Date.newInstance(2026,3,22), Last_Action__c='Upgraded'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=meta.Id, Rating__c='Buy', Target_Price__c=620.00, Last_Updated__c=Date.newInstance(2026,3,30), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Sarah Chen', Company__c=avgo.Id, Rating__c='Buy', Target_Price__c=1400.00, Last_Updated__c=Date.newInstance(2026,4,2), Last_Action__c='Reiterated'),

    // James Rodriguez — Healthcare + Financials (10 stocks)
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=lly.Id, Rating__c='Buy', Target_Price__c=950.00, Last_Updated__c=Date.newInstance(2026,4,4), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=unh.Id, Rating__c='Overweight', Target_Price__c=620.00, Last_Updated__c=Date.newInstance(2026,3,27), Last_Action__c='Upgraded'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=jnj.Id, Rating__c='Hold', Target_Price__c=170.00, Last_Updated__c=Date.newInstance(2026,3,15), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=pfe.Id, Rating__c='Underweight', Target_Price__c=26.00, Last_Updated__c=Date.newInstance(2026,3,19), Last_Action__c='Downgraded'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=abbv.Id, Rating__c='Buy', Target_Price__c=210.00, Last_Updated__c=Date.newInstance(2026,4,1), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=jpm.Id, Rating__c='Buy', Target_Price__c=250.00, Last_Updated__c=Date.newInstance(2026,3,29), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=bac.Id, Rating__c='Overweight', Target_Price__c=48.00, Last_Updated__c=Date.newInstance(2026,3,26), Last_Action__c='Upgraded'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=wfc.Id, Rating__c='Hold', Target_Price__c=62.00, Last_Updated__c=Date.newInstance(2026,3,21), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=gs.Id, Rating__c='Overweight', Target_Price__c=520.00, Last_Updated__c=Date.newInstance(2026,4,3), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='James Rodriguez', Company__c=ms.Id, Rating__c='Buy', Target_Price__c=115.00, Last_Updated__c=Date.newInstance(2026,3,24), Last_Action__c='Initiated'),

    // Priya Sharma — Energy + Consumer + Industrials + Communication (10 stocks)
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=xom.Id, Rating__c='Overweight', Target_Price__c=130.00, Last_Updated__c=Date.newInstance(2026,4,2), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=cvx.Id, Rating__c='Buy', Target_Price__c=175.00, Last_Updated__c=Date.newInstance(2026,3,28), Last_Action__c='Upgraded'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=cop.Id, Rating__c='Hold', Target_Price__c=120.00, Last_Updated__c=Date.newInstance(2026,3,20), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=cost.Id, Rating__c='Buy', Target_Price__c=950.00, Last_Updated__c=Date.newInstance(2026,4,4), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=wmt.Id, Rating__c='Overweight', Target_Price__c=85.00, Last_Updated__c=Date.newInstance(2026,3,25), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=hd.Id, Rating__c='Hold', Target_Price__c=390.00, Last_Updated__c=Date.newInstance(2026,3,18), Last_Action__c='Downgraded'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=cat.Id, Rating__c='Buy', Target_Price__c=410.00, Last_Updated__c=Date.newInstance(2026,4,1), Last_Action__c='Reiterated'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=hon.Id, Rating__c='Overweight', Target_Price__c=230.00, Last_Updated__c=Date.newInstance(2026,3,22), Last_Action__c='Initiated'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=nflx.Id, Rating__c='Buy', Target_Price__c=780.00, Last_Updated__c=Date.newInstance(2026,3,30), Last_Action__c='Upgraded'),
    new IR_Coverage__c(Analyst__c='Priya Sharma', Company__c=dis.Id, Rating__c='Hold', Target_Price__c=120.00, Last_Updated__c=Date.newInstance(2026,3,17), Last_Action__c='Reiterated')
};
insert allCoverages;
System.debug('Inserted ' + allCoverages.size() + ' IR_Coverage__c records.');


// === 5. IR_WATCHLIST__c (20) — Stocks with upcoming earnings ===
System.debug('=== Creating 20 IR_Watchlist__c records ===');

List<IR_Watchlist__c> allWatchlists = new List<IR_Watchlist__c>{
    new IR_Watchlist__c(Company__c=nvda.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,23), Added_Date__c=Date.newInstance(2026,3,1), Reason__c='AI capex cycle inflection — data center guidance critical'),
    new IR_Watchlist__c(Company__c=aapl.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,24), Added_Date__c=Date.newInstance(2026,3,5), Reason__c='Services revenue trajectory and China iPhone demand'),
    new IR_Watchlist__c(Company__c=msft.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,22), Added_Date__c=Date.newInstance(2026,3,1), Reason__c='Azure growth rate and Copilot monetization update'),
    new IR_Watchlist__c(Company__c=googl.Id, Priority__c='Medium', Earnings_Date__c=Date.newInstance(2026,4,22), Added_Date__c=Date.newInstance(2026,3,10), Reason__c='Search AI integration impact on ad revenue'),
    new IR_Watchlist__c(Company__c=amzn.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,24), Added_Date__c=Date.newInstance(2026,3,3), Reason__c='AWS re-acceleration and retail margin expansion'),
    new IR_Watchlist__c(Company__c=tsla.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,16), Added_Date__c=Date.newInstance(2026,3,8), Reason__c='Delivery numbers and FSD regulatory progress'),
    new IR_Watchlist__c(Company__c=meta.Id, Priority__c='Medium', Earnings_Date__c=Date.newInstance(2026,4,23), Added_Date__c=Date.newInstance(2026,3,12), Reason__c='Reality Labs losses and Reels monetization'),
    new IR_Watchlist__c(Company__c=lly.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,24), Added_Date__c=Date.newInstance(2026,3,2), Reason__c='Mounjaro/Zepbound supply ramp and new indication data'),
    new IR_Watchlist__c(Company__c=jpm.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,15), Added_Date__c=Date.newInstance(2026,3,1), Reason__c='NII guidance and credit quality trends — bellwether'),
    new IR_Watchlist__c(Company__c=xom.Id, Priority__c='Medium', Earnings_Date__c=Date.newInstance(2026,4,25), Added_Date__c=Date.newInstance(2026,3,15), Reason__c='Pioneer integration synergies and Permian production'),
    new IR_Watchlist__c(Company__c=avgo.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,30), Added_Date__c=Date.newInstance(2026,3,7), Reason__c='Custom AI chip orders and VMware cross-sell'),
    new IR_Watchlist__c(Company__c=cost.Id, Priority__c='Medium', Earnings_Date__c=Date.newInstance(2026,4,28), Added_Date__c=Date.newInstance(2026,3,20), Reason__c='Membership fee increase impact and comp sales'),
    new IR_Watchlist__c(Company__c=gs.Id, Priority__c='Medium', Earnings_Date__c=Date.newInstance(2026,4,15), Added_Date__c=Date.newInstance(2026,3,10), Reason__c='Trading revenue and asset management AUM growth'),
    new IR_Watchlist__c(Company__c=unh.Id, Priority__c='Medium', Earnings_Date__c=Date.newInstance(2026,4,16), Added_Date__c=Date.newInstance(2026,3,14), Reason__c='Medical cost ratio trends and Optum growth'),
    new IR_Watchlist__c(Company__c=nflx.Id, Priority__c='Medium', Earnings_Date__c=Date.newInstance(2026,4,17), Added_Date__c=Date.newInstance(2026,3,18), Reason__c='Ad tier subscriber growth and live events strategy'),
    new IR_Watchlist__c(Company__c=cat.Id, Priority__c='Low', Earnings_Date__c=Date.newInstance(2026,4,29), Added_Date__c=Date.newInstance(2026,3,22), Reason__c='Infrastructure spending cycle and dealer inventory'),
    new IR_Watchlist__c(Company__c=pfe.Id, Priority__c='Low', Earnings_Date__c=Date.newInstance(2026,4,29), Added_Date__c=Date.newInstance(2026,3,25), Reason__c='Oncology pipeline progress post-Seagen'),
    new IR_Watchlist__c(Company__c=amd.Id, Priority__c='High', Earnings_Date__c=Date.newInstance(2026,4,29), Added_Date__c=Date.newInstance(2026,3,4), Reason__c='MI300X revenue ramp vs NVDA competitive positioning'),
    new IR_Watchlist__c(Company__c=crm.Id, Priority__c='Low', Earnings_Date__c=Date.newInstance(2026,4,28), Added_Date__c=Date.newInstance(2026,3,28), Reason__c='Agentforce adoption metrics and margin trajectory'),
    new IR_Watchlist__c(Company__c=wmt.Id, Priority__c='Low', Earnings_Date__c=Date.newInstance(2026,4,17), Added_Date__c=Date.newInstance(2026,3,30), Reason__c='Walmart+ growth and advertising revenue scale')
};
insert allWatchlists;
System.debug('Inserted ' + allWatchlists.size() + ' IR_Watchlist__c records.');


// === 6. IR_RESEARCH_NOTE__c (5) — Published research briefs ===
System.debug('=== Creating 5 IR_Research_Note__c records ===');

List<IR_Research_Note__c> allNotes = new List<IR_Research_Note__c>{
    new IR_Research_Note__c(
        Company__c=nvda.Id,
        Ticker__c='NVDA',
        Analyst__c='Sarah Chen',
        Rating__c='Buy',
        Target_Price__c=1050.00,
        Generated_Date__c=DateTime.newInstance(2026,3,15,9,0,0),
        Pipeline_Run_Id__c='pipe-2026-03-15-nvda-001',
        Summary__c='NVIDIA continues to dominate the AI accelerator market with its H100 and upcoming B200 GPU architectures. Data center revenue grew 265% year-over-year in the most recent quarter, driven by hyperscaler demand for AI training and inference workloads. Management guided for continued sequential growth as supply constraints ease.\n\nThe competitive moat remains wide due to CUDA ecosystem lock-in, with over 4 million developers building on the platform. AMD MI300X is gaining some traction but remains a distant second in enterprise adoption. Custom silicon from hyperscalers addresses only a fraction of the total addressable market.\n\nWe reiterate our Buy rating with a $1,050 price target based on 35x forward earnings. Key risks include potential demand normalization post-training buildout, export restrictions to China, and customer concentration among top-5 hyperscalers.',
        Full_Brief__c='NVIDIA Corporation (NVDA) — Investment Research Brief Q1 2026\n\nExecutive Summary: NVIDIA continues to dominate the AI accelerator market with its H100 and upcoming B200 GPU architectures. Data center revenue grew 265% YoY, driven by hyperscaler demand for AI training and inference workloads. Management guided for continued sequential growth as supply constraints ease.\n\nCompetitive Position: The competitive moat remains wide due to CUDA ecosystem lock-in, with over 4 million developers on the platform. AMD MI300X is gaining traction but remains a distant second in enterprise adoption. Custom silicon from hyperscalers addresses only a fraction of the TAM.\n\nValuation: We reiterate our Buy rating with a $1,050 price target based on 35x forward earnings.\n\nInvestment Thesis: AI infrastructure spending is a multi-year secular trend. NVIDIA captures the largest share of GPU compute spend with unmatched software ecosystem advantages.\n\nCatalysts: B200 production ramp in Q2 2026; Sovereign AI deals expanding TAM; Inference workload growth as AI applications scale; Networking revenue from Spectrum-X platform.\n\nRisks: China export restrictions tightening; Customer concentration risk with top-5 hyperscalers representing 50%+ of revenue; Potential demand air pocket post-training infrastructure buildout; Custom silicon competition.',
        Thesis__c='AI infrastructure spending is a multi-year secular trend. NVIDIA captures the largest share of GPU compute spend with unmatched software ecosystem advantages.',
        Catalysts__c='B200 production ramp in Q2 2026; Sovereign AI deals expanding TAM; Inference workload growth as AI applications scale; Networking revenue from Spectrum-X platform.',
        Risks__c='China export restrictions tightening; Customer concentration risk with top-5 hyperscalers representing 50%+ of revenue; Potential demand air pocket post-training infrastructure buildout; Custom silicon competition.'
    ),
    new IR_Research_Note__c(
        Company__c=aapl.Id,
        Ticker__c='AAPL',
        Analyst__c='Sarah Chen',
        Rating__c='Buy',
        Target_Price__c=245.00,
        Generated_Date__c=DateTime.newInstance(2026,3,18,10,30,0),
        Pipeline_Run_Id__c='pipe-2026-03-18-aapl-001',
        Summary__c='Apple reported solid Q1 results with Services revenue reaching a new all-time high of $26.3B, growing 14% year-over-year. The installed base of active devices exceeded 2.3 billion, providing a durable foundation for recurring services monetization. iPhone revenue was roughly flat as the upgrade cycle for iPhone 17 builds anticipation.\n\nApple Intelligence features are driving measurable increases in device engagement and creating new monetization vectors through premium AI capabilities. The Vision Pro spatial computing platform is finding traction in enterprise use cases, though consumer adoption remains nascent.\n\nWe upgrade to Buy from Hold with a $245 price target. The services business alone justifies a significant portion of the current market cap, and we see iPhone 17 as a meaningful upgrade catalyst with on-device AI capabilities.',
        Full_Brief__c='Apple Inc. (AAPL) — Investment Research Brief Q1 2026\n\nExecutive Summary: Apple reported solid Q1 results with Services revenue reaching a new all-time high of $26.3B, growing 14% YoY. The installed base of active devices exceeded 2.3 billion, providing a durable foundation for recurring services monetization.\n\nAI Strategy: Apple Intelligence features are driving measurable increases in device engagement and creating new monetization vectors through premium AI capabilities. Vision Pro is finding traction in enterprise use cases.\n\nValuation: We upgrade to Buy from Hold with a $245 price target. The services business alone justifies a significant portion of the current market cap.\n\nInvestment Thesis: Services revenue growth and margin expansion, combined with the iPhone 17 AI-driven upgrade cycle, support premium valuation. Installed base monetization is underappreciated.\n\nCatalysts: iPhone 17 launch with enhanced Apple Intelligence; Services revenue crossing $30B quarterly run rate; India manufacturing expansion; Vision Pro enterprise adoption.\n\nRisks: China regulatory and competitive headwinds; Smartphone market saturation in developed markets; App Store regulatory pressure in EU and US; Vision Pro consumer adoption slower than expected.',
        Thesis__c='Services revenue growth and margin expansion, combined with the iPhone 17 AI-driven upgrade cycle, support premium valuation. Installed base monetization is underappreciated.',
        Catalysts__c='iPhone 17 launch with enhanced Apple Intelligence; Services revenue crossing $30B quarterly run rate; India manufacturing expansion; Vision Pro enterprise adoption.',
        Risks__c='China regulatory and competitive headwinds; Smartphone market saturation in developed markets; App Store regulatory pressure in EU and US; Vision Pro consumer adoption slower than expected.'
    ),
    new IR_Research_Note__c(
        Company__c=jpm.Id,
        Ticker__c='JPM',
        Analyst__c='James Rodriguez',
        Rating__c='Buy',
        Target_Price__c=250.00,
        Generated_Date__c=DateTime.newInstance(2026,3,20,8,0,0),
        Pipeline_Run_Id__c='pipe-2026-03-20-jpm-001',
        Summary__c='JPMorgan Chase delivered another strong quarter with record net revenue of $44.2B. Net interest income remained robust at $24.1B despite the rate cut cycle, as loan growth and deposit repricing offset lower benchmark rates. The investment banking franchise captured market share with fees up 32% year-over-year.\n\nCredit quality remains benign with net charge-offs at 62bps, below the through-cycle average. Management built reserves modestly, signaling confidence in the economic outlook. The CIB division continues to benefit from elevated M&A and IPO activity as the capital markets cycle recovers.\n\nWe maintain our Buy rating with a $250 price target. JPM trades at 2.1x tangible book value, justified given its consistent 17%+ ROTCE and dominant competitive position across all major banking verticals.',
        Full_Brief__c='JPMorgan Chase & Co. (JPM) — Investment Research Brief Q1 2026\n\nExecutive Summary: JPMorgan Chase delivered another strong quarter with record net revenue of $44.2B. Net interest income remained robust at $24.1B despite the rate cut cycle.\n\nInvestment Banking: The IB franchise captured market share with fees up 32% YoY. The CIB division continues to benefit from elevated M&A and IPO activity.\n\nCredit Quality: Net charge-offs at 62bps, below the through-cycle average. Management built reserves modestly, signaling confidence.\n\nValuation: We maintain our Buy rating with a $250 price target. JPM trades at 2.1x tangible book value, justified given its consistent 17%+ ROTCE.\n\nInvestment Thesis: Best-in-class universal bank with dominant market positions across consumer, commercial, and investment banking.\n\nCatalysts: Capital markets recovery driving IB fees; Credit card loan growth; International expansion in UK digital banking; Increased capital return as Basel III endgame clarity emerges.\n\nRisks: Credit cycle deterioration in consumer lending; NII pressure from accelerated rate cuts; Regulatory capital requirements under Basel III endgame.',
        Thesis__c='Best-in-class universal bank with dominant market positions across consumer, commercial, and investment banking. Technology investment creates sustainable competitive advantages.',
        Catalysts__c='Capital markets recovery driving IB fees; Credit card loan growth; International expansion in UK digital banking; Increased capital return as Basel III endgame clarity emerges.',
        Risks__c='Credit cycle deterioration in consumer lending; NII pressure from accelerated rate cuts; Regulatory capital requirements under Basel III endgame; Geopolitical risks affecting global markets activity.'
    ),
    new IR_Research_Note__c(
        Company__c=lly.Id,
        Ticker__c='LLY',
        Analyst__c='James Rodriguez',
        Rating__c='Buy',
        Target_Price__c=950.00,
        Generated_Date__c=DateTime.newInstance(2026,3,22,11,0,0),
        Pipeline_Run_Id__c='pipe-2026-03-22-lly-001',
        Summary__c='Eli Lilly reported exceptional results driven by the GLP-1 franchise. Mounjaro revenue reached $4.5B in the quarter while Zepbound obesity sales hit $1.8B, both exceeding consensus estimates. Supply constraints are easing as new manufacturing capacity comes online, with management guiding for significant sequential improvement in product availability.\n\nThe pipeline continues to deliver with orforglipron (oral GLP-1) showing promising Phase 3 data that could dramatically expand the addressable market. Retatrutide (triple agonist) Phase 3 results expected in H2 2026 represent the next major catalyst.\n\nWe reiterate Buy with a $950 price target. The obesity market alone could reach $100B+ by 2030, and Lilly is positioned to capture the largest share. Current valuation is demanding at 55x forward earnings but justified by the growth trajectory.',
        Full_Brief__c='Eli Lilly and Company (LLY) — Investment Research Brief Q1 2026\n\nExecutive Summary: Eli Lilly reported exceptional results driven by the GLP-1 franchise. Mounjaro revenue reached $4.5B while Zepbound obesity sales hit $1.8B, both exceeding consensus.\n\nSupply & Manufacturing: Supply constraints are easing as new manufacturing capacity comes online.\n\nPipeline: Orforglipron (oral GLP-1) showing promising Phase 3 data. Retatrutide (triple agonist) Phase 3 results expected in H2 2026.\n\nValuation: We reiterate Buy with a $950 price target. The obesity market alone could reach $100B+ by 2030.\n\nInvestment Thesis: GLP-1 franchise in obesity and diabetes represents a generational pharmaceutical opportunity.\n\nCatalysts: Orforglipron Phase 3 readout; Zepbound supply normalization; New obesity indications; International launches.\n\nRisks: GLP-1 competition from Novo Nordisk; Manufacturing scale-up execution; Pricing pressure from IRA negotiation.',
        Thesis__c='GLP-1 franchise in obesity and diabetes represents a generational pharmaceutical opportunity. Pipeline depth in oral formulations and next-gen molecules extends the growth runway beyond 2030.',
        Catalysts__c='Orforglipron Phase 3 readout; Zepbound supply normalization; New obesity indications (NASH, sleep apnea, cardiovascular); International launches in major markets.',
        Risks__c='GLP-1 competition from Novo Nordisk and emerging entrants; Manufacturing scale-up execution; Pricing pressure from IRA negotiation; Discontinuation rates in real-world obesity treatment.'
    ),
    new IR_Research_Note__c(
        Company__c=xom.Id,
        Ticker__c='XOM',
        Analyst__c='Priya Sharma',
        Rating__c='Overweight',
        Target_Price__c=130.00,
        Generated_Date__c=DateTime.newInstance(2026,3,25,14,0,0),
        Pipeline_Run_Id__c='pipe-2026-03-25-xom-001',
        Summary__c='ExxonMobil reported solid results with upstream production reaching 4.2M barrels of oil equivalent per day following the Pioneer Natural Resources integration. Permian Basin production is on track to reach 2.3M boepd by 2027, making Exxon the largest producer in the basin. Cost synergies from the Pioneer deal are running ahead of the $2B annual target.\n\nThe downstream and chemical segments benefited from improved refining margins and polyethylene demand recovery. Low Carbon Solutions is progressing with the Baytown CCS hub and lithium extraction projects, though these remain pre-revenue.\n\nWe maintain Overweight with a $130 price target. At current oil prices, Exxon generates substantial free cash flow supporting the dividend and $20B annual buyback program. The Pioneer integration provides visible production growth through decade-end.',
        Full_Brief__c='Exxon Mobil Corporation (XOM) — Investment Research Brief Q1 2026\n\nExecutive Summary: ExxonMobil reported solid results with upstream production reaching 4.2M boepd following the Pioneer Natural Resources integration. Permian Basin production on track to reach 2.3M boepd by 2027.\n\nPioneer Integration: Cost synergies running ahead of the $2B annual target. Exxon is now the largest Permian Basin producer.\n\nDownstream & Chemical: Benefited from improved refining margins and polyethylene demand recovery.\n\nLow Carbon Solutions: Baytown CCS hub and lithium extraction projects progressing, though pre-revenue.\n\nValuation: We maintain Overweight with a $130 price target. Substantial free cash flow supports the dividend and $20B annual buyback.\n\nInvestment Thesis: Pioneer integration creates the premier Permian Basin position with visible production growth and cost synergies.\n\nCatalysts: Pioneer synergy realization ahead of schedule; Permian production milestones; Guyana Phase 3+ developments; Potential for special dividends.\n\nRisks: Oil price decline below $60/bbl; Energy transition policy risk; Pioneer integration execution; Permian Basin infrastructure constraints.',
        Thesis__c='Pioneer integration creates the premier Permian Basin position with visible production growth and cost synergies. Shareholder return program is well-supported by free cash flow generation.',
        Catalysts__c='Pioneer synergy realization ahead of schedule; Permian production milestones; Guyana Phase 3+ developments; Potential for special dividends if oil prices remain elevated.',
        Risks__c='Oil price decline below $60/bbl would pressure returns; Energy transition policy risk; Pioneer integration execution; Permian Basin infrastructure constraints.'
    )
};
insert allNotes;
System.debug('Inserted ' + allNotes.size() + ' IR_Research_Note__c records.');


// === 7. IR_AUDIT_LOG__c (50) — Audit trail from last 30 days ===
System.debug('=== Creating 50 IR_Audit_Log__c records ===');

DateTime baseTime = DateTime.now();
List<IR_Audit_Log__c> allLogs = new List<IR_Audit_Log__c>();

// --- Batch 1: Standard QUERY actions (15 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-29), Trace_Id__c='trc-2026-03-01-00101', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='What is the current analyst consensus on NVDA?', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c, IR_Company__c', Decision_Rationale__c='Standard coverage query — public data only'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-28), Trace_Id__c='trc-2026-03-02-00201', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Show me all healthcare stocks with Buy ratings', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c, IR_Company__c', Decision_Rationale__c='Sector screening query — no MNPI involved'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-27), Trace_Id__c='trc-2026-03-03-00301', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='What are the upcoming earnings dates for energy sector?', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Watchlist__c, IR_Company__c', Decision_Rationale__c='Calendar query — public earnings dates'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-26), Trace_Id__c='trc-2026-03-04-00401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Compare NVDA and AMD target prices and ratings', Pipeline_Stage__c='analysis', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='Comparative analysis — internal ratings only'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-25), Trace_Id__c='trc-2026-03-05-00501', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='What is JPM current target price and thesis?', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c, IR_Research_Note__c', Decision_Rationale__c='Standard research retrieval'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-24), Trace_Id__c='trc-2026-03-06-00601', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='List all stocks on watchlist with High priority', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Watchlist__c', Decision_Rationale__c='Watchlist filter — no sensitive data'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-23), Trace_Id__c='trc-2026-03-07-00701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Show Henderson Family portfolio allocation breakdown', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Client portfolio query — authorized analyst access'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-22), Trace_Id__c='trc-2026-03-08-00801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='What are the risk factors for LLY?', Pipeline_Stage__c='analysis', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Research_Note__c, IR_Coverage__c', Decision_Rationale__c='Risk analysis from published research'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-21), Trace_Id__c='trc-2026-03-09-00901', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Show me all Overweight-rated stocks across my coverage', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='Rating filter query'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-20), Trace_Id__c='trc-2026-03-10-01001', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='What is the total market cap of my tech coverage universe?', Pipeline_Stage__c='analysis', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Company__c, IR_Coverage__c', Decision_Rationale__c='Aggregation query — public market data'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-19), Trace_Id__c='trc-2026-03-11-01101', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Show Nakamura Trust bond allocation details', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account', Decision_Rationale__c='Client allocation query — authorized access'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-18), Trace_Id__c='trc-2026-03-12-01201', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='What catalysts are upcoming for CAT and HON?', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Watchlist__c, IR_Coverage__c', Decision_Rationale__c='Catalyst screening — public information'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-17), Trace_Id__c='trc-2026-03-13-01301', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate a sector heatmap for technology coverage', Pipeline_Stage__c='analysis', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c, IR_Company__c', Decision_Rationale__c='Visualization request — public ratings data'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-16), Trace_Id__c='trc-2026-03-14-01401', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Compare GS and MS on valuation metrics', Pipeline_Stage__c='analysis', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c, IR_Company__c', Decision_Rationale__c='Peer comparison — public data'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-15), Trace_Id__c='trc-2026-03-15-01501', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Show Reeves Retirement glide path allocation', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account', Decision_Rationale__c='Client retirement allocation — authorized access'));

// --- Batch 2: RESEARCH_BRIEF actions (10 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-14), Trace_Id__c='trc-2026-03-16-01601', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate research brief for NVDA', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c', Decision_Rationale__c='Full pipeline execution — all public sources'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-13), Trace_Id__c='trc-2026-03-17-01701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate research brief for AAPL', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c', Decision_Rationale__c='Full pipeline execution — all public sources'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-12), Trace_Id__c='trc-2026-03-18-01801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate research brief for JPM', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c', Decision_Rationale__c='Full pipeline execution — all public sources'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-11), Trace_Id__c='trc-2026-03-19-01901', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate research brief for LLY', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c', Decision_Rationale__c='Full pipeline execution — all public sources'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-10), Trace_Id__c='trc-2026-03-20-02001', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Generate research brief for XOM', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c', Decision_Rationale__c='Full pipeline execution — all public sources'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-9), Trace_Id__c='trc-2026-03-21-02101', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Update NVDA brief with latest earnings data', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, IR_Research_Note__c', Decision_Rationale__c='Brief update — incremental public data'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-8), Trace_Id__c='trc-2026-03-22-02201', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate comparative brief for BAC vs WFC', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, IR_Coverage__c', Decision_Rationale__c='Peer comparison brief — public data'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-7), Trace_Id__c='trc-2026-03-23-02301', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Generate brief for COST ahead of earnings', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News', Decision_Rationale__c='Pre-earnings brief — public data'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-6), Trace_Id__c='trc-2026-03-24-02401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Generate brief for META with Reels monetization focus', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c', Decision_Rationale__c='Thematic brief — public data'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESEARCH_BRIEF', Timestamp__c=baseTime.addDays(-5), Trace_Id__c='trc-2026-03-25-02501', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Generate brief for ABBV immunology franchise update', Pipeline_Stage__c='generation', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR, Alpha Vantage, Tavily News, IR_Coverage__c', Decision_Rationale__c='Franchise deep-dive — public data'));

// --- Batch 3: COMPLIANCE_CHECK actions (8 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-14), Trace_Id__c='trc-2026-03-16-02601', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Pre-trade compliance check: Henderson NVDA position sizing', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Henderson NVDA allocation at 15% — exceeds 10% single-stock limit but within client-approved exception'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-13), Trace_Id__c='trc-2026-03-17-02701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Concentration alert: Henderson tech allocation review', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Henderson 60% tech allocation flagged — client has signed aggressive growth mandate waiver'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-12), Trace_Id__c='trc-2026-03-18-02801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Pre-trade compliance check: Nakamura bond rebalance', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account', Decision_Rationale__c='Nakamura 40% bond allocation within conservative mandate parameters'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-11), Trace_Id__c='trc-2026-03-19-02901', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Concentration alert: Singh NVDA position at 12%', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Singh NVDA at 12% — exceeds 10% threshold, escalated to compliance officer'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-10), Trace_Id__c='trc-2026-03-20-03001', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Concentration alert: Blackwood NVDA position at 14%', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Blackwood NVDA at 14% — family office has documented concentration exception'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-9), Trace_Id__c='trc-2026-03-21-03101', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Pre-trade compliance check: Reeves retirement glide path', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account', Decision_Rationale__c='Reeves near-retirement allocation 30% equity / 55% bonds / 15% cash — within glide path parameters'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-8), Trace_Id__c='trc-2026-03-22-03201', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Restricted list check before XOM trade recommendation', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='XOM not on restricted list — trade recommendation cleared'));
allLogs.add(new IR_Audit_Log__c(Action__c='COMPLIANCE_CHECK', Timestamp__c=baseTime.addDays(-7), Trace_Id__c='trc-2026-03-23-03301', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Quarterly suitability review: Morrison Capital portfolio', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Morrison portfolio within moderate risk mandate — no action required'));

// --- Batch 4: TRADE_REVIEW actions (5 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-6), Trace_Id__c='trc-2026-03-24-03401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Review proposed NVDA add for Henderson Family', Pipeline_Stage__c='review', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Trade aligns with Buy rating and client aggressive growth mandate'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-5), Trace_Id__c='trc-2026-03-25-03501', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Review proposed LLY position for Ashford FO', Pipeline_Stage__c='review', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='LLY Buy rating supports position initiation within healthcare allocation'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-4), Trace_Id__c='trc-2026-03-26-03601', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Review proposed XOM trim for Great Lakes Pension', Pipeline_Stage__c='review', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='Trim aligns with Overweight (not Buy) rating and pension rebalancing schedule'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-3), Trace_Id__c='trc-2026-03-27-03701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Review proposed MSFT add for Meridian FO', Pipeline_Stage__c='review', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='MSFT Buy rating supports add within tech allocation limits'));
allLogs.add(new IR_Audit_Log__c(Action__c='TRADE_REVIEW', Timestamp__c=baseTime.addDays(-2), Trace_Id__c='trc-2026-03-28-03801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Review proposed JPM position increase for Sunbelt Endowment', Pipeline_Stage__c='review', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Account, IR_Coverage__c', Decision_Rationale__c='JPM Buy rating and endowment income mandate support position increase'));

// --- Batch 5: DATA_ACCESS actions (5 entries) ---
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-15), Trace_Id__c='trc-2026-03-15-03901', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='SEC EDGAR 10-K retrieval for NVDA', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR MCP', Decision_Rationale__c='Public filing retrieval — no restrictions'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-14), Trace_Id__c='trc-2026-03-16-04001', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Alpha Vantage real-time quote for JPM', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Alpha Vantage MCP', Decision_Rationale__c='Public market data retrieval'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-13), Trace_Id__c='trc-2026-03-17-04101', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Tavily news search for XOM Pioneer integration', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Tavily News MCP', Decision_Rationale__c='Public news retrieval'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-12), Trace_Id__c='trc-2026-03-18-04201', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='SEC EDGAR 8-K retrieval for MSFT', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='SEC EDGAR MCP', Decision_Rationale__c='Public filing retrieval'));
allLogs.add(new IR_Audit_Log__c(Action__c='DATA_ACCESS', Timestamp__c=baseTime.addDays(-11), Trace_Id__c='trc-2026-03-19-04301', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Alpha Vantage historical data for LLY', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='Alpha Vantage MCP', Decision_Rationale__c='Public market data retrieval'));

// --- Batch 6: MNPI VIOLATIONS — 3 entries with MNPI_Flag__c = true, Compliance_Status__c = 'FAIL' ---
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-4), Trace_Id__c='trc-2026-03-26-04401', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='What are the pending NVDA insider transactions before earnings?', Pipeline_Stage__c='compliance', Compliance_Status__c='FAIL', MNPI_Flag__c=true, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='MNPI VIOLATION: Query attempted to access material non-public information about pending insider transactions. Blocked by compliance filter. Incident escalated to compliance officer.'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-3), Trace_Id__c='trc-2026-03-27-04501', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Show me NVDA preliminary revenue figures ahead of announcement', Pipeline_Stage__c='compliance', Compliance_Status__c='FAIL', MNPI_Flag__c=true, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='MNPI VIOLATION: Query attempted to access pre-announcement revenue data. This constitutes material non-public information. Query blocked. Second NVDA MNPI incident — mandatory compliance review triggered.'));
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-2), Trace_Id__c='trc-2026-03-28-04601', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='What is MSFT unannounced acquisition target?', Pipeline_Stage__c='compliance', Compliance_Status__c='FAIL', MNPI_Flag__c=true, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='MNPI VIOLATION: Query attempted to access material non-public M&A information. Blocked by compliance filter. Incident logged and escalated.'));

// --- Batch 7: RESTRICTED_LIST_ADD — 3 entries for TSLA, GS, PFE ---
allLogs.add(new IR_Audit_Log__c(Action__c='RESTRICTED_LIST_ADD', Timestamp__c=baseTime.addDays(-10), Trace_Id__c='trc-2026-03-20-04701', Agent__c='OpenClaw-IR', Analyst__c='Sarah Chen', Query__c='Add TSLA to restricted list — pending corporate action', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='TSLA added to restricted list due to pending corporate action. All trading suspended until further notice. Compliance notification sent to all coverage analysts.'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESTRICTED_LIST_ADD', Timestamp__c=baseTime.addDays(-8), Trace_Id__c='trc-2026-03-22-04801', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Add GS to restricted list — firm involvement in advisory mandate', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='GS added to restricted list due to firm advisory mandate involvement. Research publication suspended. Trading restricted for all firm accounts.'));
allLogs.add(new IR_Audit_Log__c(Action__c='RESTRICTED_LIST_ADD', Timestamp__c=baseTime.addDays(-6), Trace_Id__c='trc-2026-03-24-04901', Agent__c='OpenClaw-IR', Analyst__c='James Rodriguez', Query__c='Add PFE to restricted list — material non-public clinical trial data', Pipeline_Stage__c='compliance', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c', Decision_Rationale__c='PFE added to restricted list due to access to material non-public clinical trial results. All trading and research publication suspended pending public disclosure.'));

// --- Entry 50: Standard query to round out to 50 ---
allLogs.add(new IR_Audit_Log__c(Action__c='QUERY', Timestamp__c=baseTime.addDays(-1), Trace_Id__c='trc-2026-03-29-05001', Agent__c='OpenClaw-IR', Analyst__c='Priya Sharma', Query__c='Show me the full coverage universe with latest ratings', Pipeline_Stage__c='retrieval', Compliance_Status__c='PASS', MNPI_Flag__c=false, Data_Sources_Used__c='IR_Coverage__c, IR_Company__c', Decision_Rationale__c='Standard coverage universe query — public data only'));

insert allLogs;
System.debug('Inserted ' + allLogs.size() + ' IR_Audit_Log__c records.');

// === SUMMARY ===
System.debug('============================================');
System.debug('=== SEED DATA LOAD COMPLETE ===');
System.debug('  Accounts:          ' + allAccounts.size());
System.debug('  Contacts:          ' + allContacts.size());
System.debug('  IR_Company__c:     ' + allCompanies.size());
System.debug('  IR_Coverage__c:    ' + allCoverages.size());
System.debug('  IR_Watchlist__c:   ' + allWatchlists.size());
System.debug('  IR_Research_Note:  ' + allNotes.size());
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
    System.debug(LoggingLevel.ERROR, '=== SEED DATA ERROR ===');
    System.debug(LoggingLevel.ERROR, 'Message: ' + e.getMessage());
    System.debug(LoggingLevel.ERROR, 'Type: ' + e.getTypeName());
    System.debug(LoggingLevel.ERROR, 'Stack: ' + e.getStackTraceString());
    throw e;
}
