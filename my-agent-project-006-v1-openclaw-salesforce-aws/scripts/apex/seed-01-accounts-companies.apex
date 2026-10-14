// ============================================================================
// Seed Data Part 1 of 3 — Accounts, Contacts, IR_Company__c
// Run with: sf apex run --file scripts/apex/seed-01-accounts-companies.apex
// Idempotent: deletes existing IR_* records and test accounts before inserting.
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
Account henderson = new Account(Name='Henderson Family', BillingCity='Greenwich', BillingCountry='United States', BillingState='Connecticut', Industry='Financial Services');
Account nakamura = new Account(Name='Nakamura Trust', BillingCity='San Francisco', BillingCountry='United States', BillingState='California', Industry='Financial Services');
Account reeves = new Account(Name='Reeves Retirement', BillingCity='Scottsdale', BillingCountry='United States', BillingState='Arizona', Industry='Financial Services');
Account patel = new Account(Name='Patel Holdings', BillingCity='Houston', BillingCountry='United States', BillingState='Texas', Industry='Financial Services');
Account morrison = new Account(Name='Morrison Capital', BillingCity='Chicago', BillingCountry='United States', BillingState='Illinois', Industry='Financial Services');
Account oconnell = new Account(Name='O\'Connell Estate', BillingCity='Boston', BillingCountry='United States', BillingState='Massachusetts', Industry='Financial Services');
Account zhang = new Account(Name='Zhang Family Trust', BillingCity='Seattle', BillingCountry='United States', BillingState='Washington', Industry='Financial Services');
Account kowalski = new Account(Name='Kowalski Wealth', BillingCity='Denver', BillingCountry='United States', BillingState='Colorado', Industry='Financial Services');
Account dubois = new Account(Name='DuBois Legacy Fund', BillingCity='New Orleans', BillingCountry='United States', BillingState='Louisiana', Industry='Financial Services');
Account singh = new Account(Name='Singh Growth Portfolio', BillingCity='Austin', BillingCountry='United States', BillingState='Texas', Industry='Financial Services');

// 5 Family Offices
Account blackwood = new Account(Name='Blackwood Family Office', BillingCity='New York', BillingCountry='United States', BillingState='New York', Industry='Financial Services');
Account ashford = new Account(Name='Ashford & Partners FO', BillingCity='Palm Beach', BillingCountry='United States', BillingState='Florida', Industry='Financial Services');
Account meridian = new Account(Name='Meridian Family Office', BillingCity='Dallas', BillingCountry='United States', BillingState='Texas', Industry='Financial Services');
Account sterling = new Account(Name='Sterling House FO', BillingCity='Philadelphia', BillingCountry='United States', BillingState='Pennsylvania', Industry='Financial Services');
Account pacifica = new Account(Name='Pacifica Family Office', BillingCity='Los Angeles', BillingCountry='United States', BillingState='California', Industry='Financial Services');

// 5 Institutional Investors
Account greatLakes = new Account(Name='Great Lakes Pension Fund', BillingCity='Detroit', BillingCountry='United States', BillingState='Michigan', Industry='Financial Services');
Account sunbelt = new Account(Name='Sunbelt Endowment', BillingCity='Atlanta', BillingCountry='United States', BillingState='Georgia', Industry='Financial Services');
Account cascadeIns = new Account(Name='Cascade Insurance Group', BillingCity='Portland', BillingCountry='United States', BillingState='Oregon', Industry='Financial Services');
Account midwestFdn = new Account(Name='Midwest Foundation Trust', BillingCity='Minneapolis', BillingCountry='United States', BillingState='Minnesota', Industry='Financial Services');
Account harborRe = new Account(Name='Harbor Re Insurance', BillingCity='Hartford', BillingCountry='United States', BillingState='Connecticut', Industry='Financial Services');

// 5 Corporate Accounts
Account techbridge = new Account(Name='TechBridge Ventures', BillingCity='San Jose', BillingCountry='United States', BillingState='California', Industry='Financial Services');
Account irongate = new Account(Name='Irongate Capital Corp', BillingCity='Charlotte', BillingCountry='United States', BillingState='North Carolina', Industry='Financial Services');
Account blueridge = new Account(Name='Blue Ridge Holdings', BillingCity='Richmond', BillingCountry='United States', BillingState='Virginia', Industry='Financial Services');
Account summitCorp = new Account(Name='Summit Corporate Treasury', BillingCity='Salt Lake City', BillingCountry='United States', BillingState='Utah', Industry='Financial Services');
Account bayshore = new Account(Name='Bayshore Capital Group', BillingCity='Miami', BillingCountry='United States', BillingState='Florida', Industry='Financial Services');

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
IR_Company__c nvda = new IR_Company__c(Name='NVIDIA Corporation', Ticker__c='NVDA', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=3200000000000.0);
IR_Company__c aapl = new IR_Company__c(Name='Apple Inc.', Ticker__c='AAPL', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=2900000000000.0);
IR_Company__c msft = new IR_Company__c(Name='Microsoft Corporation', Ticker__c='MSFT', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=3100000000000.0);
IR_Company__c googl = new IR_Company__c(Name='Alphabet Inc.', Ticker__c='GOOGL', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=2100000000000.0);
IR_Company__c amzn = new IR_Company__c(Name='Amazon.com Inc.', Ticker__c='AMZN', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=2000000000000.0);
IR_Company__c amd = new IR_Company__c(Name='Advanced Micro Devices', Ticker__c='AMD', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=280000000000.0);
IR_Company__c tsla = new IR_Company__c(Name='Tesla Inc.', Ticker__c='TSLA', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=800000000000.0);
IR_Company__c crm = new IR_Company__c(Name='Salesforce Inc.', Ticker__c='CRM', Sector__c='Technology', Exchange__c='NYSE', Market_Cap__c=275000000000.0);
IR_Company__c meta = new IR_Company__c(Name='Meta Platforms Inc.', Ticker__c='META', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=1400000000000.0);
IR_Company__c avgo = new IR_Company__c(Name='Broadcom Inc.', Ticker__c='AVGO', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=750000000000.0);

// Healthcare (5)
IR_Company__c lly = new IR_Company__c(Name='Eli Lilly and Company', Ticker__c='LLY', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=800000000000.0);
IR_Company__c unh = new IR_Company__c(Name='UnitedHealth Group', Ticker__c='UNH', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=480000000000.0);
IR_Company__c jnj = new IR_Company__c(Name='Johnson & Johnson', Ticker__c='JNJ', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=380000000000.0);
IR_Company__c pfe = new IR_Company__c(Name='Pfizer Inc.', Ticker__c='PFE', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=160000000000.0);
IR_Company__c abbv = new IR_Company__c(Name='AbbVie Inc.', Ticker__c='ABBV', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=310000000000.0);

// Financials (5)
IR_Company__c jpm = new IR_Company__c(Name='JPMorgan Chase & Co.', Ticker__c='JPM', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=580000000000.0);
IR_Company__c bac = new IR_Company__c(Name='Bank of America Corp', Ticker__c='BAC', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=310000000000.0);
IR_Company__c wfc = new IR_Company__c(Name='Wells Fargo & Company', Ticker__c='WFC', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=200000000000.0);
IR_Company__c gs = new IR_Company__c(Name='Goldman Sachs Group', Ticker__c='GS', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=155000000000.0);
IR_Company__c ms = new IR_Company__c(Name='Morgan Stanley', Ticker__c='MS', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=165000000000.0);

// Energy (3)
IR_Company__c xom = new IR_Company__c(Name='Exxon Mobil Corporation', Ticker__c='XOM', Sector__c='Energy', Exchange__c='NYSE', Market_Cap__c=460000000000.0);
IR_Company__c cvx = new IR_Company__c(Name='Chevron Corporation', Ticker__c='CVX', Sector__c='Energy', Exchange__c='NYSE', Market_Cap__c=290000000000.0);
IR_Company__c cop = new IR_Company__c(Name='ConocoPhillips', Ticker__c='COP', Sector__c='Energy', Exchange__c='NYSE', Market_Cap__c=140000000000.0);

// Consumer (3)
IR_Company__c cost = new IR_Company__c(Name='Costco Wholesale Corp', Ticker__c='COST', Sector__c='Consumer', Exchange__c='NASDAQ', Market_Cap__c=370000000000.0);
IR_Company__c wmt = new IR_Company__c(Name='Walmart Inc.', Ticker__c='WMT', Sector__c='Consumer', Exchange__c='NYSE', Market_Cap__c=480000000000.0);
IR_Company__c hd = new IR_Company__c(Name='The Home Depot Inc.', Ticker__c='HD', Sector__c='Consumer', Exchange__c='NYSE', Market_Cap__c=360000000000.0);

// Industrials (2)
IR_Company__c cat = new IR_Company__c(Name='Caterpillar Inc.', Ticker__c='CAT', Sector__c='Industrials', Exchange__c='NYSE', Market_Cap__c=180000000000.0);
IR_Company__c hon = new IR_Company__c(Name='Honeywell International', Ticker__c='HON', Sector__c='Industrials', Exchange__c='NYSE', Market_Cap__c=145000000000.0);

// Communication Services (2)
IR_Company__c nflx = new IR_Company__c(Name='Netflix Inc.', Ticker__c='NFLX', Sector__c='Communication Services', Exchange__c='NASDAQ', Market_Cap__c=310000000000.0);
IR_Company__c dis = new IR_Company__c(Name='The Walt Disney Company', Ticker__c='DIS', Sector__c='Communication Services', Exchange__c='NYSE', Market_Cap__c=200000000000.0);

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

// === SUMMARY ===
System.debug('============================================');
System.debug('=== SEED PART 1 COMPLETE ===');
System.debug('  Accounts:          ' + allAccounts.size());
System.debug('  Contacts:          ' + allContacts.size());
System.debug('  IR_Company__c:     ' + allCompanies.size());
System.debug('============================================');

} catch (Exception e) {
    System.debug(LoggingLevel.ERROR, '=== SEED PART 1 ERROR ===');
    System.debug(LoggingLevel.ERROR, 'Message: ' + e.getMessage());
    System.debug(LoggingLevel.ERROR, 'Type: ' + e.getTypeName());
    System.debug(LoggingLevel.ERROR, 'Stack: ' + e.getStackTraceString());
    throw e;
}
