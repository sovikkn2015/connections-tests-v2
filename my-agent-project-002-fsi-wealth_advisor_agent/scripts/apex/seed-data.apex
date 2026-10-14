// Seed data for Wealth Advisor Agent - 5 Households
// Run with: sf apex run --file scripts/apex/seed-data.apex

// Clean existing data
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
    // Johnson
    new WA_Financial_Account__c(Name='Johnson IRA', Client__c=sarah.Id, Type__c='IRA', Balance__c=450000, Allocation__c='60% Equity / 30% Fixed / 10% Cash', YTD_Return__c=7.2),
    new WA_Financial_Account__c(Name='Johnson 401k', Client__c=tom.Id, Type__c='401k', Balance__c=820000, Allocation__c='70% Equity / 25% Fixed / 5% Cash', YTD_Return__c=8.5),
    new WA_Financial_Account__c(Name='Johnson Family Trust', Client__c=sarah.Id, Type__c='Trust', Balance__c=1530000, Allocation__c='50% Equity / 40% Fixed / 10% Cash', YTD_Return__c=5.8),
    // Chen
    new WA_Financial_Account__c(Name='Chen Brokerage', Client__c=wei.Id, Type__c='Brokerage', Balance__c=2200000, Allocation__c='80% Equity / 15% Fixed / 5% Cash', YTD_Return__c=12.3),
    new WA_Financial_Account__c(Name='Chen Roth IRA', Client__c=wei.Id, Type__c='Roth IRA', Balance__c=850000, Allocation__c='75% Equity / 20% Fixed / 5% Cash', YTD_Return__c=11.1),
    new WA_Financial_Account__c(Name='Chen 529 Plan', Client__c=lin.Id, Type__c='529 Plan', Balance__c=1050000, Allocation__c='65% Equity / 30% Fixed / 5% Cash', YTD_Return__c=9.4),
    // Martinez
    new WA_Financial_Account__c(Name='Martinez IRA', Client__c=carlos.Id, Type__c='IRA', Balance__c=680000, Allocation__c='40% Equity / 50% Fixed / 10% Cash', YTD_Return__c=4.1),
    new WA_Financial_Account__c(Name='Martinez 401k', Client__c=maria.Id, Type__c='401k', Balance__c=520000, Allocation__c='35% Equity / 55% Fixed / 10% Cash', YTD_Return__c=3.8),
    // Patel
    new WA_Financial_Account__c(Name='Patel Brokerage', Client__c=raj.Id, Type__c='Brokerage', Balance__c=3200000, Allocation__c='65% Equity / 25% Fixed / 10% Cash', YTD_Return__c=9.7),
    new WA_Financial_Account__c(Name='Patel Trust', Client__c=raj.Id, Type__c='Trust', Balance__c=2100000, Allocation__c='55% Equity / 35% Fixed / 10% Cash', YTD_Return__c=6.9),
    new WA_Financial_Account__c(Name='Patel Roth IRA', Client__c=priya.Id, Type__c='Roth IRA', Balance__c=1200000, Allocation__c='60% Equity / 30% Fixed / 10% Cash', YTD_Return__c=7.8),
    // Williams
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

System.debug('Seed data loaded: 5 households, 10 clients, ' + accounts.size() + ' accounts, ' + goals.size() + ' goals, ' + meetings.size() + ' meetings');
