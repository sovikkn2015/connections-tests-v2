// Seed data for Wealth Advisor Agent Phase 1-5
// Run with: sf apex run --file scripts/apex/seed-data.apex

// Clean existing data (new objects first due to lookups)
delete [SELECT Id FROM WA_Referral__c];
delete [SELECT Id FROM WA_Transaction__c];
delete [SELECT Id FROM WA_Meeting__c];
delete [SELECT Id FROM WA_Financial_Goal__c];
delete [SELECT Id FROM WA_Financial_Account__c];
delete [SELECT Id FROM WA_Client__c];
delete [SELECT Id FROM WA_Household__c];

// === HOUSEHOLDS ===
WA_Household__c johnson = new WA_Household__c(Name='Johnson Family', Total_AUM__c=2800000, Risk_Profile__c='Moderate', Advisor__c='Alex Morgan');
WA_Household__c chen = new WA_Household__c(Name='Chen Family', Total_AUM__c=4100000, Risk_Profile__c='Aggressive', Advisor__c='Alex Morgan');
WA_Household__c martinez = new WA_Household__c(Name='Martinez Family', Total_AUM__c=1200000, Risk_Profile__c='Conservative', Advisor__c='Alex Morgan');
WA_Household__c patel = new WA_Household__c(Name='Patel Family', Total_AUM__c=6500000, Risk_Profile__c='Moderate', Advisor__c='Alex Morgan');
WA_Household__c williams = new WA_Household__c(Name='Williams Family', Total_AUM__c=890000, Risk_Profile__c='Growth', Advisor__c='Alex Morgan');
insert new List<WA_Household__c>{johnson, chen, martinez, patel, williams};

// === CLIENTS ===
WA_Client__c sarah = new WA_Client__c(Name='Sarah Johnson', Household__c=johnson.Id, Email__c='sarah.johnson@email.com', Phone__c='555-0101', Role__c='Primary');
WA_Client__c tom = new WA_Client__c(Name='Tom Johnson', Household__c=johnson.Id, Email__c='tom.johnson@email.com', Phone__c='555-0102', Role__c='Spouse');
WA_Client__c wei = new WA_Client__c(Name='Wei Chen', Household__c=chen.Id, Email__c='wei.chen@email.com', Phone__c='555-0201', Role__c='Primary');
WA_Client__c lin = new WA_Client__c(Name='Lin Chen', Household__c=chen.Id, Email__c='lin.chen@email.com', Phone__c='555-0202', Role__c='Spouse');
WA_Client__c carlos = new WA_Client__c(Name='Carlos Martinez', Household__c=martinez.Id, Email__c='carlos.martinez@email.com', Phone__c='555-0301', Role__c='Primary');
WA_Client__c maria = new WA_Client__c(Name='Maria Martinez', Household__c=martinez.Id, Email__c='maria.martinez@email.com', Phone__c='555-0302', Role__c='Spouse');
WA_Client__c raj = new WA_Client__c(Name='Raj Patel', Household__c=patel.Id, Email__c='raj.patel@email.com', Phone__c='555-0401', Role__c='Primary');
WA_Client__c priya = new WA_Client__c(Name='Priya Patel', Household__c=patel.Id, Email__c='priya.patel@email.com', Phone__c='555-0402', Role__c='Spouse');
WA_Client__c james = new WA_Client__c(Name='James Williams', Household__c=williams.Id, Email__c='james.williams@email.com', Phone__c='555-0501', Role__c='Primary');
WA_Client__c olivia = new WA_Client__c(Name='Olivia Williams', Household__c=williams.Id, Email__c='olivia.williams@email.com', Phone__c='555-0502', Role__c='Spouse');
insert new List<WA_Client__c>{sarah, tom, wei, lin, carlos, maria, raj, priya, james, olivia};

// === FINANCIAL ACCOUNTS ===
List<WA_Financial_Account__c> accounts = new List<WA_Financial_Account__c>{
    // Johnson (Moderate)
    new WA_Financial_Account__c(Name='Johnson IRA', Client__c=sarah.Id, Type__c='IRA', Balance__c=450000, Allocation__c='60% Equity / 30% Fixed / 10% Cash', YTD_Return__c=7.2),
    new WA_Financial_Account__c(Name='Johnson 401k', Client__c=tom.Id, Type__c='401k', Balance__c=820000, Allocation__c='70% Equity / 25% Fixed / 5% Cash', YTD_Return__c=8.5),
    new WA_Financial_Account__c(Name='Johnson Family Trust', Client__c=sarah.Id, Type__c='Trust', Balance__c=1530000, Allocation__c='50% Equity / 40% Fixed / 10% Cash', YTD_Return__c=5.8),
    // Chen (Aggressive)
    new WA_Financial_Account__c(Name='Chen Brokerage', Client__c=wei.Id, Type__c='Brokerage', Balance__c=2200000, Allocation__c='80% Equity / 15% Fixed / 5% Cash', YTD_Return__c=12.3),
    new WA_Financial_Account__c(Name='Chen Roth IRA', Client__c=wei.Id, Type__c='Roth IRA', Balance__c=850000, Allocation__c='75% Equity / 20% Fixed / 5% Cash', YTD_Return__c=11.1),
    new WA_Financial_Account__c(Name='Chen 529 Plan', Client__c=lin.Id, Type__c='529 Plan', Balance__c=1050000, Allocation__c='65% Equity / 30% Fixed / 5% Cash', YTD_Return__c=9.4),
    // Martinez (Conservative)
    new WA_Financial_Account__c(Name='Martinez IRA', Client__c=carlos.Id, Type__c='IRA', Balance__c=680000, Allocation__c='40% Equity / 50% Fixed / 10% Cash', YTD_Return__c=4.1),
    new WA_Financial_Account__c(Name='Martinez 401k', Client__c=maria.Id, Type__c='401k', Balance__c=520000, Allocation__c='35% Equity / 55% Fixed / 10% Cash', YTD_Return__c=3.8),
    // Patel (Moderate)
    new WA_Financial_Account__c(Name='Patel Brokerage', Client__c=raj.Id, Type__c='Brokerage', Balance__c=3200000, Allocation__c='65% Equity / 25% Fixed / 10% Cash', YTD_Return__c=9.7),
    new WA_Financial_Account__c(Name='Patel Trust', Client__c=raj.Id, Type__c='Trust', Balance__c=2100000, Allocation__c='55% Equity / 35% Fixed / 10% Cash', YTD_Return__c=6.9),
    new WA_Financial_Account__c(Name='Patel Roth IRA', Client__c=priya.Id, Type__c='Roth IRA', Balance__c=1200000, Allocation__c='60% Equity / 30% Fixed / 10% Cash', YTD_Return__c=7.8),
    // Williams (Growth)
    new WA_Financial_Account__c(Name='Williams 401k', Client__c=james.Id, Type__c='401k', Balance__c=520000, Allocation__c='70% Equity / 20% Fixed / 10% Cash', YTD_Return__c=10.2),
    new WA_Financial_Account__c(Name='Williams IRA', Client__c=olivia.Id, Type__c='IRA', Balance__c=370000, Allocation__c='65% Equity / 25% Fixed / 10% Cash', YTD_Return__c=8.9)
};
insert accounts;

// === FINANCIAL GOALS ===
List<WA_Financial_Goal__c> goals = new List<WA_Financial_Goal__c>{
    new WA_Financial_Goal__c(Name='Retirement', Client__c=sarah.Id, Target_Amount__c=3000000, Current_Amount__c=2800000, Target_Date__c=Date.newInstance(2035, 1, 1)),
    new WA_Financial_Goal__c(Name='College Fund - Emma', Client__c=sarah.Id, Target_Amount__c=200000, Current_Amount__c=145000, Target_Date__c=Date.newInstance(2030, 9, 1)),
    new WA_Financial_Goal__c(Name='Early Retirement', Client__c=wei.Id, Target_Amount__c=5000000, Current_Amount__c=4100000, Target_Date__c=Date.newInstance(2032, 6, 1)),
    new WA_Financial_Goal__c(Name='College Fund - Kids', Client__c=lin.Id, Target_Amount__c=400000, Current_Amount__c=1050000, Target_Date__c=Date.newInstance(2034, 9, 1)),
    new WA_Financial_Goal__c(Name='Retirement', Client__c=carlos.Id, Target_Amount__c=1500000, Current_Amount__c=1200000, Target_Date__c=Date.newInstance(2038, 1, 1)),
    new WA_Financial_Goal__c(Name='Vacation Home', Client__c=carlos.Id, Target_Amount__c=350000, Current_Amount__c=120000, Target_Date__c=Date.newInstance(2029, 6, 1)),
    new WA_Financial_Goal__c(Name='Retirement', Client__c=raj.Id, Target_Amount__c=8000000, Current_Amount__c=6500000, Target_Date__c=Date.newInstance(2033, 1, 1)),
    new WA_Financial_Goal__c(Name='Philanthropy Fund', Client__c=raj.Id, Target_Amount__c=1000000, Current_Amount__c=650000, Target_Date__c=Date.newInstance(2030, 12, 31)),
    new WA_Financial_Goal__c(Name='Retirement', Client__c=james.Id, Target_Amount__c=1200000, Current_Amount__c=890000, Target_Date__c=Date.newInstance(2040, 1, 1)),
    new WA_Financial_Goal__c(Name='Home Down Payment', Client__c=james.Id, Target_Amount__c=150000, Current_Amount__c=85000, Target_Date__c=Date.newInstance(2027, 6, 1))
};
insert goals;

// === MEETINGS ===
List<WA_Meeting__c> meetings = new List<WA_Meeting__c>{
    new WA_Meeting__c(Name='Annual Portfolio Review', Client__c=sarah.Id, Date_Time__c=DateTime.now().addDays(7), Location__c='Office - Conference Room A', Notes__c='Discuss retirement timeline and college fund progress', Action_Items__c='Review trust allocation; Update beneficiary designations'),
    new WA_Meeting__c(Name='Q2 Performance Review', Client__c=wei.Id, Date_Time__c=DateTime.now().addDays(14), Location__c='Virtual - Zoom', Notes__c='Review aggressive growth strategy performance', Action_Items__c='Evaluate tax-loss harvesting opportunities'),
    new WA_Meeting__c(Name='Retirement Planning Check-in', Client__c=carlos.Id, Date_Time__c=DateTime.now().addDays(3), Location__c='Office - Conference Room B', Notes__c='Carlos wants to discuss moving retirement date earlier', Action_Items__c='Run updated retirement projections; Review vacation home savings plan'),
    new WA_Meeting__c(Name='Estate Planning Discussion', Client__c=raj.Id, Date_Time__c=DateTime.now().addDays(21), Location__c='Client Home', Notes__c='Discuss philanthropy fund structure and estate plan updates', Action_Items__c='Coordinate with estate attorney; Review trust documents'),
    new WA_Meeting__c(Name='New Client Onboarding Follow-up', Client__c=james.Id, Date_Time__c=DateTime.now().addDays(5), Location__c='Office - Conference Room A', Notes__c='Follow up on initial onboarding, review risk tolerance questionnaire', Action_Items__c='Finalize investment policy statement; Set up automatic contributions')
};
insert meetings;

// === TRANSACTIONS (50+ across all clients) ===
List<WA_Transaction__c> txns = new List<WA_Transaction__c>();

// Sarah Johnson transactions (Johnson IRA)
txns.add(new WA_Transaction__c(Name='TXN-001', Client__c=sarah.Id, Account__c=accounts[0].Id, Type__c='Buy', Amount__c=25000, Date__c=Date.today().addDays(-5), Symbol__c='VTI', Description__c='Vanguard Total Stock Market ETF'));
txns.add(new WA_Transaction__c(Name='TXN-002', Client__c=sarah.Id, Account__c=accounts[0].Id, Type__c='Sell', Amount__c=15000, Date__c=Date.today().addDays(-12), Symbol__c='BND', Description__c='Vanguard Total Bond Market ETF'));
txns.add(new WA_Transaction__c(Name='TXN-003', Client__c=sarah.Id, Account__c=accounts[0].Id, Type__c='Dividend', Amount__c=1250, Date__c=Date.today().addDays(-15), Symbol__c='VTI', Description__c='Quarterly dividend'));
txns.add(new WA_Transaction__c(Name='TXN-004', Client__c=sarah.Id, Account__c=accounts[0].Id, Type__c='Fee', Amount__c=125, Date__c=Date.today().addDays(-30), Symbol__c='', Description__c='Advisory fee Q1'));
txns.add(new WA_Transaction__c(Name='TXN-005', Client__c=sarah.Id, Account__c=accounts[2].Id, Type__c='Buy', Amount__c=50000, Date__c=Date.today().addDays(-8), Symbol__c='AAPL', Description__c='Apple Inc'));
txns.add(new WA_Transaction__c(Name='TXN-006', Client__c=sarah.Id, Account__c=accounts[2].Id, Type__c='Sell', Amount__c=30000, Date__c=Date.today().addDays(-20), Symbol__c='MSFT', Description__c='Microsoft Corp'));
txns.add(new WA_Transaction__c(Name='TXN-007', Client__c=sarah.Id, Account__c=accounts[2].Id, Type__c='Dividend', Amount__c=3500, Date__c=Date.today().addDays(-25), Symbol__c='JNJ', Description__c='Johnson & Johnson dividend'));

// Tom Johnson transactions (Johnson 401k)
txns.add(new WA_Transaction__c(Name='TXN-008', Client__c=tom.Id, Account__c=accounts[1].Id, Type__c='Buy', Amount__c=5000, Date__c=Date.today().addDays(-1), Symbol__c='SPY', Description__c='S&P 500 ETF - payroll contribution'));
txns.add(new WA_Transaction__c(Name='TXN-009', Client__c=tom.Id, Account__c=accounts[1].Id, Type__c='Buy', Amount__c=5000, Date__c=Date.today().addDays(-15), Symbol__c='SPY', Description__c='S&P 500 ETF - payroll contribution'));
txns.add(new WA_Transaction__c(Name='TXN-010', Client__c=tom.Id, Account__c=accounts[1].Id, Type__c='Buy', Amount__c=5000, Date__c=Date.today().addDays(-30), Symbol__c='SPY', Description__c='S&P 500 ETF - payroll contribution'));

// Wei Chen transactions (Chen Brokerage)
txns.add(new WA_Transaction__c(Name='TXN-011', Client__c=wei.Id, Account__c=accounts[3].Id, Type__c='Buy', Amount__c=100000, Date__c=Date.today().addDays(-3), Symbol__c='NVDA', Description__c='NVIDIA Corp'));
txns.add(new WA_Transaction__c(Name='TXN-012', Client__c=wei.Id, Account__c=accounts[3].Id, Type__c='Buy', Amount__c=75000, Date__c=Date.today().addDays(-7), Symbol__c='TSLA', Description__c='Tesla Inc'));
txns.add(new WA_Transaction__c(Name='TXN-013', Client__c=wei.Id, Account__c=accounts[3].Id, Type__c='Sell', Amount__c=50000, Date__c=Date.today().addDays(-10), Symbol__c='META', Description__c='Meta Platforms'));
txns.add(new WA_Transaction__c(Name='TXN-014', Client__c=wei.Id, Account__c=accounts[3].Id, Type__c='Sell', Amount__c=80000, Date__c=Date.today().addDays(-14), Symbol__c='AMZN', Description__c='Amazon.com'));
txns.add(new WA_Transaction__c(Name='TXN-015', Client__c=wei.Id, Account__c=accounts[3].Id, Type__c='Dividend', Amount__c=5500, Date__c=Date.today().addDays(-18), Symbol__c='AAPL', Description__c='Apple quarterly dividend'));
txns.add(new WA_Transaction__c(Name='TXN-016', Client__c=wei.Id, Account__c=accounts[3].Id, Type__c='Fee', Amount__c=550, Date__c=Date.today().addDays(-30), Symbol__c='', Description__c='Advisory fee Q1'));

// Wei Chen (Chen Roth IRA)
txns.add(new WA_Transaction__c(Name='TXN-017', Client__c=wei.Id, Account__c=accounts[4].Id, Type__c='Buy', Amount__c=35000, Date__c=Date.today().addDays(-6), Symbol__c='QQQ', Description__c='Nasdaq 100 ETF'));
txns.add(new WA_Transaction__c(Name='TXN-018', Client__c=wei.Id, Account__c=accounts[4].Id, Type__c='Sell', Amount__c=20000, Date__c=Date.today().addDays(-22), Symbol__c='GOOGL', Description__c='Alphabet Inc'));
txns.add(new WA_Transaction__c(Name='TXN-019', Client__c=wei.Id, Account__c=accounts[4].Id, Type__c='Dividend', Amount__c=2100, Date__c=Date.today().addDays(-28), Symbol__c='MSFT', Description__c='Microsoft dividend'));

// Lin Chen (Chen 529 Plan)
txns.add(new WA_Transaction__c(Name='TXN-020', Client__c=lin.Id, Account__c=accounts[5].Id, Type__c='Buy', Amount__c=10000, Date__c=Date.today().addDays(-2), Symbol__c='VGIT', Description__c='Vanguard Intermediate-Term Treasury'));
txns.add(new WA_Transaction__c(Name='TXN-021', Client__c=lin.Id, Account__c=accounts[5].Id, Type__c='Buy', Amount__c=10000, Date__c=Date.today().addDays(-32), Symbol__c='VTI', Description__c='Vanguard Total Stock Market'));

// Carlos Martinez transactions (Martinez IRA)
txns.add(new WA_Transaction__c(Name='TXN-022', Client__c=carlos.Id, Account__c=accounts[6].Id, Type__c='Buy', Amount__c=15000, Date__c=Date.today().addDays(-4), Symbol__c='AGG', Description__c='iShares Core US Aggregate Bond'));
txns.add(new WA_Transaction__c(Name='TXN-023', Client__c=carlos.Id, Account__c=accounts[6].Id, Type__c='Sell', Amount__c=8000, Date__c=Date.today().addDays(-11), Symbol__c='VTI', Description__c='Vanguard Total Stock Market'));
txns.add(new WA_Transaction__c(Name='TXN-024', Client__c=carlos.Id, Account__c=accounts[6].Id, Type__c='Dividend', Amount__c=2800, Date__c=Date.today().addDays(-16), Symbol__c='AGG', Description__c='Bond ETF distribution'));
txns.add(new WA_Transaction__c(Name='TXN-025', Client__c=carlos.Id, Account__c=accounts[6].Id, Type__c='Fee', Amount__c=170, Date__c=Date.today().addDays(-30), Symbol__c='', Description__c='Advisory fee Q1'));
txns.add(new WA_Transaction__c(Name='TXN-026', Client__c=carlos.Id, Account__c=accounts[6].Id, Type__c='Buy', Amount__c=12000, Date__c=Date.today().addDays(-35), Symbol__c='TIP', Description__c='iShares TIPS Bond ETF'));

// Maria Martinez (Martinez 401k)
txns.add(new WA_Transaction__c(Name='TXN-027', Client__c=maria.Id, Account__c=accounts[7].Id, Type__c='Buy', Amount__c=3500, Date__c=Date.today().addDays(-1), Symbol__c='VBTLX', Description__c='Vanguard Total Bond - payroll'));
txns.add(new WA_Transaction__c(Name='TXN-028', Client__c=maria.Id, Account__c=accounts[7].Id, Type__c='Buy', Amount__c=3500, Date__c=Date.today().addDays(-15), Symbol__c='VBTLX', Description__c='Vanguard Total Bond - payroll'));
txns.add(new WA_Transaction__c(Name='TXN-029', Client__c=maria.Id, Account__c=accounts[7].Id, Type__c='Dividend', Amount__c=1100, Date__c=Date.today().addDays(-20), Symbol__c='VBTLX', Description__c='Bond fund distribution'));

// Raj Patel transactions (Patel Brokerage)
txns.add(new WA_Transaction__c(Name='TXN-030', Client__c=raj.Id, Account__c=accounts[8].Id, Type__c='Buy', Amount__c=200000, Date__c=Date.today().addDays(-2), Symbol__c='VTI', Description__c='Vanguard Total Stock Market'));
txns.add(new WA_Transaction__c(Name='TXN-031', Client__c=raj.Id, Account__c=accounts[8].Id, Type__c='Sell', Amount__c=150000, Date__c=Date.today().addDays(-9), Symbol__c='AAPL', Description__c='Apple Inc - profit taking'));
txns.add(new WA_Transaction__c(Name='TXN-032', Client__c=raj.Id, Account__c=accounts[8].Id, Type__c='Buy', Amount__c=100000, Date__c=Date.today().addDays(-13), Symbol__c='MSFT', Description__c='Microsoft Corp'));
txns.add(new WA_Transaction__c(Name='TXN-033', Client__c=raj.Id, Account__c=accounts[8].Id, Type__c='Dividend', Amount__c=8000, Date__c=Date.today().addDays(-17), Symbol__c='VTI', Description__c='Quarterly dividend'));
txns.add(new WA_Transaction__c(Name='TXN-034', Client__c=raj.Id, Account__c=accounts[8].Id, Type__c='Fee', Amount__c=800, Date__c=Date.today().addDays(-30), Symbol__c='', Description__c='Advisory fee Q1'));
txns.add(new WA_Transaction__c(Name='TXN-035', Client__c=raj.Id, Account__c=accounts[8].Id, Type__c='Sell', Amount__c=75000, Date__c=Date.today().addDays(-21), Symbol__c='GOOGL', Description__c='Alphabet - rebalancing'));

// Raj Patel (Patel Trust)
txns.add(new WA_Transaction__c(Name='TXN-036', Client__c=raj.Id, Account__c=accounts[9].Id, Type__c='Buy', Amount__c=50000, Date__c=Date.today().addDays(-5), Symbol__c='BND', Description__c='Vanguard Total Bond Market'));
txns.add(new WA_Transaction__c(Name='TXN-037', Client__c=raj.Id, Account__c=accounts[9].Id, Type__c='Dividend', Amount__c=4200, Date__c=Date.today().addDays(-19), Symbol__c='VYM', Description__c='Vanguard High Dividend Yield'));
txns.add(new WA_Transaction__c(Name='TXN-038', Client__c=raj.Id, Account__c=accounts[9].Id, Type__c='Sell', Amount__c=40000, Date__c=Date.today().addDays(-26), Symbol__c='JNJ', Description__c='Johnson & Johnson'));

// Priya Patel (Patel Roth IRA)
txns.add(new WA_Transaction__c(Name='TXN-039', Client__c=priya.Id, Account__c=accounts[10].Id, Type__c='Buy', Amount__c=7000, Date__c=Date.today().addDays(-3), Symbol__c='VOO', Description__c='Vanguard S&P 500 ETF'));
txns.add(new WA_Transaction__c(Name='TXN-040', Client__c=priya.Id, Account__c=accounts[10].Id, Type__c='Dividend', Amount__c=1800, Date__c=Date.today().addDays(-15), Symbol__c='SCHD', Description__c='Schwab US Dividend Equity'));
txns.add(new WA_Transaction__c(Name='TXN-041', Client__c=priya.Id, Account__c=accounts[10].Id, Type__c='Buy', Amount__c=7000, Date__c=Date.today().addDays(-33), Symbol__c='VOO', Description__c='Vanguard S&P 500 ETF'));

// James Williams transactions (Williams 401k)
txns.add(new WA_Transaction__c(Name='TXN-042', Client__c=james.Id, Account__c=accounts[11].Id, Type__c='Buy', Amount__c=4000, Date__c=Date.today().addDays(-1), Symbol__c='VGT', Description__c='Vanguard Info Tech ETF - payroll'));
txns.add(new WA_Transaction__c(Name='TXN-043', Client__c=james.Id, Account__c=accounts[11].Id, Type__c='Buy', Amount__c=4000, Date__c=Date.today().addDays(-15), Symbol__c='VGT', Description__c='Vanguard Info Tech ETF - payroll'));
txns.add(new WA_Transaction__c(Name='TXN-044', Client__c=james.Id, Account__c=accounts[11].Id, Type__c='Buy', Amount__c=4000, Date__c=Date.today().addDays(-30), Symbol__c='VGT', Description__c='Vanguard Info Tech ETF - payroll'));
txns.add(new WA_Transaction__c(Name='TXN-045', Client__c=james.Id, Account__c=accounts[11].Id, Type__c='Dividend', Amount__c=650, Date__c=Date.today().addDays(-18), Symbol__c='VGT', Description__c='Quarterly dividend'));
txns.add(new WA_Transaction__c(Name='TXN-046', Client__c=james.Id, Account__c=accounts[11].Id, Type__c='Fee', Amount__c=130, Date__c=Date.today().addDays(-30), Symbol__c='', Description__c='Advisory fee Q1'));

// Olivia Williams (Williams IRA)
txns.add(new WA_Transaction__c(Name='TXN-047', Client__c=olivia.Id, Account__c=accounts[12].Id, Type__c='Buy', Amount__c=10000, Date__c=Date.today().addDays(-4), Symbol__c='VXUS', Description__c='Vanguard Total International Stock'));
txns.add(new WA_Transaction__c(Name='TXN-048', Client__c=olivia.Id, Account__c=accounts[12].Id, Type__c='Sell', Amount__c=5000, Date__c=Date.today().addDays(-16), Symbol__c='EFA', Description__c='iShares MSCI EAFE'));
txns.add(new WA_Transaction__c(Name='TXN-049', Client__c=olivia.Id, Account__c=accounts[12].Id, Type__c='Dividend', Amount__c=450, Date__c=Date.today().addDays(-22), Symbol__c='VXUS', Description__c='International dividend'));
txns.add(new WA_Transaction__c(Name='TXN-050', Client__c=olivia.Id, Account__c=accounts[12].Id, Type__c='Buy', Amount__c=8000, Date__c=Date.today().addDays(-35), Symbol__c='VWO', Description__c='Vanguard Emerging Markets'));
txns.add(new WA_Transaction__c(Name='TXN-051', Client__c=olivia.Id, Account__c=accounts[12].Id, Type__c='Fee', Amount__c=92, Date__c=Date.today().addDays(-30), Symbol__c='', Description__c='Advisory fee Q1'));
txns.add(new WA_Transaction__c(Name='TXN-052', Client__c=olivia.Id, Account__c=accounts[12].Id, Type__c='Transfer', Amount__c=15000, Date__c=Date.today().addDays(-40), Symbol__c='', Description__c='Transfer from savings'));

insert txns;

// === REFERRALS (one per household, mix of statuses) ===
List<WA_Referral__c> referrals = new List<WA_Referral__c>{
    new WA_Referral__c(Name='Johnson Referral', Client__c=sarah.Id, Source__c='Dr. Robert Kim', Source_Type__c='Client', Date__c=Date.newInstance(2023, 3, 15), Status__c='Converted', Value__c=2800000),
    new WA_Referral__c(Name='Chen Referral', Client__c=wei.Id, Source__c='TechVentures Annual Gala', Source_Type__c='Event', Date__c=Date.newInstance(2022, 11, 8), Status__c='Converted', Value__c=4100000),
    new WA_Referral__c(Name='Martinez Referral', Client__c=carlos.Id, Source__c='First National Bank - Maria Lopez', Source_Type__c='Partner', Date__c=Date.newInstance(2024, 1, 20), Status__c='Contacted', Value__c=1500000),
    new WA_Referral__c(Name='Patel Referral', Client__c=raj.Id, Source__c='Sarah Johnson', Source_Type__c='Client', Date__c=Date.newInstance(2021, 6, 10), Status__c='Converted', Value__c=6500000),
    new WA_Referral__c(Name='Williams Referral', Client__c=james.Id, Source__c='LinkedIn Campaign Q4', Source_Type__c='Marketing', Date__c=Date.newInstance(2024, 10, 5), Status__c='New', Value__c=1200000)
};
insert referrals;

System.debug('Seed data loaded: 5 households, 10 clients, ' + accounts.size() + ' accounts, ' + goals.size() + ' goals, ' + meetings.size() + ' meetings, ' + txns.size() + ' transactions, ' + referrals.size() + ' referrals');
