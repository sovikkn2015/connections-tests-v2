// ============================================================================
// Seed Data Part 4 of 4 — FSC Financial Accounts & Holdings
// Run with: sf apex run --file scripts/apex/seed-04-financial-holdings.apex
// Requires: Salesforce Financial Services Cloud (FSC) managed package.
// Idempotent: deletes existing FinServ holdings/accounts before inserting.
// If FSC is not installed, prints a message and exits cleanly.
// ============================================================================

try {

// === FSC AVAILABILITY CHECK ===
// Attempt a describe call on the managed object. If FSC is not installed,
// this will throw an exception caught by the outer try/catch.
Schema.SObjectType holdingType = Schema.getGlobalDescribe().get('FinServ__FinancialHolding__c');
Schema.SObjectType finAcctType = Schema.getGlobalDescribe().get('FinServ__FinancialAccount__c');

if (holdingType == null || finAcctType == null) {
    System.debug('============================================');
    System.debug('FSC not enabled — skipping holdings seed data');
    System.debug('FinServ__FinancialAccount__c and FinServ__FinancialHolding__c');
    System.debug('are managed package objects from Financial Services Cloud.');
    System.debug('Install FSC to use holdings data in the pipeline.');
    System.debug('============================================');
    // Exit cleanly — no error thrown
} else {

// === CLEAN SLATE — delete existing FSC test data ===
System.debug('=== Deleting existing FinServ holdings and financial accounts ===');

// Delete holdings first (child), then financial accounts (parent)
List<SObject> existingHoldings = Database.query('SELECT Id FROM FinServ__FinancialHolding__c');
if (!existingHoldings.isEmpty()) {
    delete existingHoldings;
    System.debug('Deleted ' + existingHoldings.size() + ' existing holdings.');
}

List<SObject> existingFinAccts = Database.query(
    'SELECT Id FROM FinServ__FinancialAccount__c WHERE Name LIKE \'%Brokerage%\' OR Name LIKE \'%Retirement%\' OR Name LIKE \'%Trust Account%\''
);
if (!existingFinAccts.isEmpty()) {
    delete existingFinAccts;
    System.debug('Deleted ' + existingFinAccts.size() + ' existing financial accounts.');
}
System.debug('Clean slate complete.');

// === LOAD EXISTING ACCOUNTS (from seed-01) ===
Map<String, Id> acctMap = new Map<String, Id>();
for (Account a : [SELECT Id, Name FROM Account WHERE Industry = 'Financial Services']) {
    acctMap.put(a.Name, a.Id);
}
System.debug('Found ' + acctMap.size() + ' existing client accounts.');

if (acctMap.isEmpty()) {
    System.debug('ERROR: No client accounts found. Run seed-01-accounts-companies.apex first.');
} else {

// === 1. FINANCIAL ACCOUNTS (15) — spread across client accounts ===
System.debug('=== Creating 15 FinServ__FinancialAccount__c records ===');

// Map of account name → list of financial account configs {name, type}
List<Map<String, String>> finAcctConfigs = new List<Map<String, String>>{
    new Map<String, String>{'owner' => 'Henderson Family', 'name' => 'Henderson Brokerage', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Henderson Family', 'name' => 'Henderson Retirement', 'type' => 'Retirement'},
    new Map<String, String>{'owner' => 'Nakamura Trust', 'name' => 'Nakamura Trust Account', 'type' => 'Trust'},
    new Map<String, String>{'owner' => 'Patel Holdings', 'name' => 'Patel Brokerage', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Morrison Capital', 'name' => 'Morrison Growth', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Zhang Family Trust', 'name' => 'Zhang Trust Account', 'type' => 'Trust'},
    new Map<String, String>{'owner' => 'Blackwood Family Office', 'name' => 'Blackwood Core', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Blackwood Family Office', 'name' => 'Blackwood Retirement', 'type' => 'Retirement'},
    new Map<String, String>{'owner' => 'Ashford & Partners FO', 'name' => 'Ashford Growth', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Meridian Family Office', 'name' => 'Meridian Core', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Great Lakes Pension Fund', 'name' => 'Great Lakes Equity', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Sunbelt Endowment', 'name' => 'Sunbelt Growth', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Cascade Insurance Group', 'name' => 'Cascade Fixed Income', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'TechBridge Ventures', 'name' => 'TechBridge Equity', 'type' => 'Brokerage'},
    new Map<String, String>{'owner' => 'Bayshore Capital Group', 'name' => 'Bayshore Core', 'type' => 'Brokerage'}
};

List<SObject> finAccts = new List<SObject>();
Map<String, SObject> finAcctByName = new Map<String, SObject>();

for (Map<String, String> cfg : finAcctConfigs) {
    Id ownerId = acctMap.get(cfg.get('owner'));
    if (ownerId == null) {
        System.debug('WARN: Account not found: ' + cfg.get('owner') + ' — skipping.');
        continue;
    }
    SObject fa = finAcctType.newSObject();
    fa.put('Name', cfg.get('name'));
    fa.put('FinServ__PrimaryOwner__c', ownerId);
    fa.put('FinServ__FinancialAccountType__c', cfg.get('type'));
    finAccts.add(fa);
    finAcctByName.put(cfg.get('name'), fa);
}
insert finAccts;
System.debug('Inserted ' + finAccts.size() + ' Financial Accounts.');

// === 2. FINANCIAL HOLDINGS (60) — mix of tickers across financial accounts ===
System.debug('=== Creating 60 FinServ__FinancialHolding__c records ===');

// Ticker → approximate current price (for seed data only)
Map<String, Decimal> tickerPrices = new Map<String, Decimal>{
    'NVDA' => 135.00, 'AAPL' => 195.00, 'MSFT' => 430.00, 'GOOGL' => 175.00,
    'AMZN' => 190.00, 'META' => 510.00, 'TSLA' => 250.00, 'JPM' => 200.00,
    'GS' => 470.00, 'CRM' => 270.00, 'AVGO' => 170.00, 'LLY' => 790.00,
    'UNH' => 520.00, 'JNJ' => 155.00, 'XOM' => 110.00
};

// Holdings config: {finAcctName, ticker, shares}
// Spread across 15 financial accounts, 4 holdings each = 60 total
List<Map<String, Object>> holdingConfigs = new List<Map<String, Object>>();

// Henderson Brokerage (4 holdings — tech heavy)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Brokerage', 'ticker' => 'NVDA', 'shares' => 500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Brokerage', 'ticker' => 'AAPL', 'shares' => 800});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Brokerage', 'ticker' => 'MSFT', 'shares' => 300});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Brokerage', 'ticker' => 'GOOGL', 'shares' => 400});

// Henderson Retirement (4 holdings — diversified)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Retirement', 'ticker' => 'JPM', 'shares' => 200});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Retirement', 'ticker' => 'JNJ', 'shares' => 350});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Retirement', 'ticker' => 'UNH', 'shares' => 150});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Henderson Retirement', 'ticker' => 'XOM', 'shares' => 400});

// Nakamura Trust Account (4 holdings — growth)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Nakamura Trust Account', 'ticker' => 'NVDA', 'shares' => 1000});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Nakamura Trust Account', 'ticker' => 'AMZN', 'shares' => 600});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Nakamura Trust Account', 'ticker' => 'META', 'shares' => 300});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Nakamura Trust Account', 'ticker' => 'TSLA', 'shares' => 450});

// Patel Brokerage (4 holdings — balanced)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Patel Brokerage', 'ticker' => 'MSFT', 'shares' => 250});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Patel Brokerage', 'ticker' => 'AAPL', 'shares' => 500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Patel Brokerage', 'ticker' => 'GS', 'shares' => 100});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Patel Brokerage', 'ticker' => 'LLY', 'shares' => 80});

// Morrison Growth (4 holdings — tech + financials)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Morrison Growth', 'ticker' => 'NVDA', 'shares' => 750});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Morrison Growth', 'ticker' => 'GOOGL', 'shares' => 350});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Morrison Growth', 'ticker' => 'JPM', 'shares' => 300});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Morrison Growth', 'ticker' => 'CRM', 'shares' => 200});

// Zhang Trust Account (4 holdings — conservative)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Zhang Trust Account', 'ticker' => 'AAPL', 'shares' => 600});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Zhang Trust Account', 'ticker' => 'MSFT', 'shares' => 400});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Zhang Trust Account', 'ticker' => 'JNJ', 'shares' => 500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Zhang Trust Account', 'ticker' => 'UNH', 'shares' => 200});

// Blackwood Core (4 holdings — large cap tech)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Core', 'ticker' => 'NVDA', 'shares' => 2000});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Core', 'ticker' => 'META', 'shares' => 500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Core', 'ticker' => 'AMZN', 'shares' => 800});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Core', 'ticker' => 'AVGO', 'shares' => 600});

// Blackwood Retirement (4 holdings — income)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Retirement', 'ticker' => 'JPM', 'shares' => 400});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Retirement', 'ticker' => 'GS', 'shares' => 150});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Retirement', 'ticker' => 'XOM', 'shares' => 500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Blackwood Retirement', 'ticker' => 'JNJ', 'shares' => 300});

// Ashford Growth (4 holdings — momentum)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Ashford Growth', 'ticker' => 'NVDA', 'shares' => 1200});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Ashford Growth', 'ticker' => 'TSLA', 'shares' => 600});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Ashford Growth', 'ticker' => 'META', 'shares' => 400});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Ashford Growth', 'ticker' => 'AAPL', 'shares' => 700});

// Meridian Core (4 holdings — diversified)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Meridian Core', 'ticker' => 'MSFT', 'shares' => 500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Meridian Core', 'ticker' => 'GOOGL', 'shares' => 300});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Meridian Core', 'ticker' => 'AMZN', 'shares' => 400});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Meridian Core', 'ticker' => 'LLY', 'shares' => 120});

// Great Lakes Equity (4 holdings — institutional)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Great Lakes Equity', 'ticker' => 'NVDA', 'shares' => 3000});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Great Lakes Equity', 'ticker' => 'AAPL', 'shares' => 2000});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Great Lakes Equity', 'ticker' => 'MSFT', 'shares' => 1500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Great Lakes Equity', 'ticker' => 'AMZN', 'shares' => 1000});

// Sunbelt Growth (4 holdings — growth + healthcare)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Sunbelt Growth', 'ticker' => 'NVDA', 'shares' => 800});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Sunbelt Growth', 'ticker' => 'LLY', 'shares' => 200});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Sunbelt Growth', 'ticker' => 'META', 'shares' => 350});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Sunbelt Growth', 'ticker' => 'TSLA', 'shares' => 500});

// Cascade Fixed Income (4 holdings — defensive)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Cascade Fixed Income', 'ticker' => 'JNJ', 'shares' => 600});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Cascade Fixed Income', 'ticker' => 'UNH', 'shares' => 250});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Cascade Fixed Income', 'ticker' => 'XOM', 'shares' => 700});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Cascade Fixed Income', 'ticker' => 'JPM', 'shares' => 350});

// TechBridge Equity (4 holdings — pure tech)
holdingConfigs.add(new Map<String, Object>{'fa' => 'TechBridge Equity', 'ticker' => 'NVDA', 'shares' => 1500});
holdingConfigs.add(new Map<String, Object>{'fa' => 'TechBridge Equity', 'ticker' => 'AVGO', 'shares' => 800});
holdingConfigs.add(new Map<String, Object>{'fa' => 'TechBridge Equity', 'ticker' => 'CRM', 'shares' => 400});
holdingConfigs.add(new Map<String, Object>{'fa' => 'TechBridge Equity', 'ticker' => 'GOOGL', 'shares' => 500});

// Bayshore Core (4 holdings — balanced)
holdingConfigs.add(new Map<String, Object>{'fa' => 'Bayshore Core', 'ticker' => 'AAPL', 'shares' => 900});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Bayshore Core', 'ticker' => 'NVDA', 'shares' => 600});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Bayshore Core', 'ticker' => 'GS', 'shares' => 200});
holdingConfigs.add(new Map<String, Object>{'fa' => 'Bayshore Core', 'ticker' => 'AMZN', 'shares' => 350});

// === INSERT HOLDINGS ===
// Build a map of financial account Name → Id for lookups
Map<String, Id> faIdMap = new Map<String, Id>();
for (SObject fa : finAccts) {
    faIdMap.put((String)fa.get('Name'), fa.Id);
}

List<SObject> allHoldings = new List<SObject>();
for (Map<String, Object> cfg : holdingConfigs) {
    String faName = (String)cfg.get('fa');
    String ticker = (String)cfg.get('ticker');
    Integer shares = (Integer)cfg.get('shares');
    Decimal price = tickerPrices.get(ticker);

    Id faId = faIdMap.get(faName);
    if (faId == null) {
        System.debug('WARN: Financial account not found: ' + faName + ' — skipping holding.');
        continue;
    }
    if (price == null) {
        System.debug('WARN: No price for ticker: ' + ticker + ' — skipping.');
        continue;
    }

    SObject h = holdingType.newSObject();
    h.put('Name', ticker);
    h.put('FinServ__FinancialAccount__c', faId);
    h.put('FinServ__Shares__c', Decimal.valueOf(shares));
    h.put('FinServ__Price__c', price);
    h.put('FinServ__MarketValue__c', price * shares);
    allHoldings.add(h);
}
insert allHoldings;
System.debug('Inserted ' + allHoldings.size() + ' Financial Holdings.');

// === SUMMARY ===
System.debug('============================================');
System.debug('=== SEED PART 4 COMPLETE ===');
System.debug('  Financial Accounts:  ' + finAccts.size());
System.debug('  Financial Holdings:  ' + allHoldings.size());
System.debug('============================================');

} // end if acctMap not empty
} // end if FSC available

} catch (Exception e) {
    // If FSC objects don't exist, the Schema.getGlobalDescribe or Database.query
    // will throw. This is expected on non-FSC orgs.
    if (e.getMessage() != null && (e.getMessage().contains('FinServ__') || e.getMessage().contains('sObject type') || e.getMessage().contains('Invalid'))) {
        System.debug('============================================');
        System.debug('FSC not enabled — skipping holdings seed data');
        System.debug('Error: ' + e.getMessage());
        System.debug('This is expected on orgs without Financial Services Cloud.');
        System.debug('============================================');
    } else {
        System.debug(LoggingLevel.ERROR, '=== SEED PART 4 ERROR ===');
        System.debug(LoggingLevel.ERROR, 'Message: ' + e.getMessage());
        System.debug(LoggingLevel.ERROR, 'Type: ' + e.getTypeName());
        System.debug(LoggingLevel.ERROR, 'Stack: ' + e.getStackTraceString());
        throw e;
    }
}
