public with sharing class IR_SeedDataRunner {
    public static void run() {
        delete [SELECT Id FROM IR_Research_Note__c];
        delete [SELECT Id FROM IR_Watchlist__c];
        delete [SELECT Id FROM IR_Coverage__c];
        delete [SELECT Id FROM IR_Audit_Log__c];
        delete [SELECT Id FROM IR_Company__c];

        IR_Company__c nvda = new IR_Company__c(Name='NVIDIA Corporation', Ticker__c='NVDA', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=2800000000000.00, Last_Price__c=135.50, Earnings_Date__c=Date.newInstance(2026, 5, 28));
        IR_Company__c aapl = new IR_Company__c(Name='Apple Inc', Ticker__c='AAPL', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=3200000000000.00, Last_Price__c=198.75, Earnings_Date__c=Date.newInstance(2026, 4, 30));
        IR_Company__c jpm  = new IR_Company__c(Name='JPMorgan Chase', Ticker__c='JPM', Sector__c='Financials', Exchange__c='NYSE', Market_Cap__c=680000000000.00, Last_Price__c=245.30, Earnings_Date__c=Date.newInstance(2026, 4, 14));
        IR_Company__c unh  = new IR_Company__c(Name='UnitedHealth Group', Ticker__c='UNH', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=520000000000.00, Last_Price__c=580.20, Earnings_Date__c=Date.newInstance(2026, 4, 15));
        IR_Company__c amzn = new IR_Company__c(Name='Amazon.com', Ticker__c='AMZN', Sector__c='Consumer Discretionary', Exchange__c='NASDAQ', Market_Cap__c=2100000000000.00, Last_Price__c=195.40, Earnings_Date__c=Date.newInstance(2026, 4, 29));
        IR_Company__c xom  = new IR_Company__c(Name='Exxon Mobil', Ticker__c='XOM', Sector__c='Energy', Exchange__c='NYSE', Market_Cap__c=480000000000.00, Last_Price__c=112.80, Earnings_Date__c=Date.newInstance(2026, 5, 1));
        IR_Company__c msft = new IR_Company__c(Name='Microsoft', Ticker__c='MSFT', Sector__c='Technology', Exchange__c='NASDAQ', Market_Cap__c=3100000000000.00, Last_Price__c=420.60, Earnings_Date__c=Date.newInstance(2026, 4, 29));
        IR_Company__c jnj  = new IR_Company__c(Name='Johnson & Johnson', Ticker__c='JNJ', Sector__c='Healthcare', Exchange__c='NYSE', Market_Cap__c=380000000000.00, Last_Price__c=158.90, Earnings_Date__c=Date.newInstance(2026, 4, 15));
        IR_Company__c cat  = new IR_Company__c(Name='Caterpillar', Ticker__c='CAT', Sector__c='Industrials', Exchange__c='NYSE', Market_Cap__c=180000000000.00, Last_Price__c=365.40, Earnings_Date__c=Date.newInstance(2026, 4, 28));
        IR_Company__c nee  = new IR_Company__c(Name='NextEra Energy', Ticker__c='NEE', Sector__c='Utilities', Exchange__c='NYSE', Market_Cap__c=155000000000.00, Last_Price__c=76.20, Earnings_Date__c=Date.newInstance(2026, 4, 22));
        List<IR_Company__c> companies = new List<IR_Company__c>{nvda, aapl, jpm, unh, amzn, xom, msft, jnj, cat, nee};
        insert companies;

        List<IR_Coverage__c> coverages = new List<IR_Coverage__c>{
            new IR_Coverage__c(Name='Kim-NVDA', Company__c=nvda.Id, Analyst__c='Sarah Kim', Rating__c='Buy', Target_Price__c=180.00, Last_Updated__c=Date.today().addDays(-3)),
            new IR_Coverage__c(Name='Kim-AAPL', Company__c=aapl.Id, Analyst__c='Sarah Kim', Rating__c='Strong Buy', Target_Price__c=210.00, Last_Updated__c=Date.today().addDays(-5)),
            new IR_Coverage__c(Name='Kim-MSFT', Company__c=msft.Id, Analyst__c='Sarah Kim', Rating__c='Buy', Target_Price__c=460.00, Last_Updated__c=Date.today().addDays(-7)),
            new IR_Coverage__c(Name='Kim-AMZN', Company__c=amzn.Id, Analyst__c='Sarah Kim', Rating__c='Buy', Target_Price__c=225.00, Last_Updated__c=Date.today().addDays(-10)),
            new IR_Coverage__c(Name='Chen-JPM', Company__c=jpm.Id, Analyst__c='David Chen', Rating__c='Buy', Target_Price__c=270.00, Last_Updated__c=Date.today().addDays(-2)),
            new IR_Coverage__c(Name='Chen-XOM', Company__c=xom.Id, Analyst__c='David Chen', Rating__c='Hold', Target_Price__c=115.00, Last_Updated__c=Date.today().addDays(-6)),
            new IR_Coverage__c(Name='Chen-CAT', Company__c=cat.Id, Analyst__c='David Chen', Rating__c='Buy', Target_Price__c=390.00, Last_Updated__c=Date.today().addDays(-8)),
            new IR_Coverage__c(Name='Chen-NEE', Company__c=nee.Id, Analyst__c='David Chen', Rating__c='Hold', Target_Price__c=78.00, Last_Updated__c=Date.today().addDays(-14)),
            new IR_Coverage__c(Name='Rodriguez-UNH', Company__c=unh.Id, Analyst__c='Maria Rodriguez', Rating__c='Strong Buy', Target_Price__c=640.00, Last_Updated__c=Date.today().addDays(-1)),
            new IR_Coverage__c(Name='Rodriguez-JNJ', Company__c=jnj.Id, Analyst__c='Maria Rodriguez', Rating__c='Hold', Target_Price__c=165.00, Last_Updated__c=Date.today().addDays(-4)),
            new IR_Coverage__c(Name='Rodriguez-AAPL', Company__c=aapl.Id, Analyst__c='Maria Rodriguez', Rating__c='Buy', Target_Price__c=205.00, Last_Updated__c=Date.today().addDays(-9)),
            new IR_Coverage__c(Name='Rodriguez-MSFT', Company__c=msft.Id, Analyst__c='Maria Rodriguez', Rating__c='Buy', Target_Price__c=450.00, Last_Updated__c=Date.today().addDays(-12)),
            new IR_Coverage__c(Name='Park-AMZN', Company__c=amzn.Id, Analyst__c='James Park', Rating__c='Buy', Target_Price__c=220.00, Last_Updated__c=Date.today().addDays(-2)),
            new IR_Coverage__c(Name='Park-CAT', Company__c=cat.Id, Analyst__c='James Park', Rating__c='Buy', Target_Price__c=400.00, Last_Updated__c=Date.today().addDays(-5)),
            new IR_Coverage__c(Name='Park-XOM', Company__c=xom.Id, Analyst__c='James Park', Rating__c='Sell', Target_Price__c=95.00, Last_Updated__c=Date.today().addDays(-11)),
            new IR_Coverage__c(Name='Park-JNJ', Company__c=jnj.Id, Analyst__c='James Park', Rating__c='Buy', Target_Price__c=175.00, Last_Updated__c=Date.today().addDays(-15)),
            new IR_Coverage__c(Name='Sharma-NEE', Company__c=nee.Id, Analyst__c='Priya Sharma', Rating__c='Buy', Target_Price__c=85.00, Last_Updated__c=Date.today().addDays(-1)),
            new IR_Coverage__c(Name='Sharma-NVDA', Company__c=nvda.Id, Analyst__c='Priya Sharma', Rating__c='Hold', Target_Price__c=145.00, Last_Updated__c=Date.today().addDays(-4)),
            new IR_Coverage__c(Name='Sharma-JPM', Company__c=jpm.Id, Analyst__c='Priya Sharma', Rating__c='Buy', Target_Price__c=260.00, Last_Updated__c=Date.today().addDays(-7)),
            new IR_Coverage__c(Name='Sharma-UNH', Company__c=unh.Id, Analyst__c='Priya Sharma', Rating__c='Strong Buy', Target_Price__c=620.00, Last_Updated__c=Date.today().addDays(-13))
        };
        insert coverages;

        List<IR_Watchlist__c> watchlist = new List<IR_Watchlist__c>{
            new IR_Watchlist__c(Name='Watch-NVDA', Company__c=nvda.Id, Analyst__c='Sarah Kim', Priority__c='High', Reason__c='Earnings next week — data center revenue guidance critical', Added_Date__c=Date.today().addDays(-3)),
            new IR_Watchlist__c(Name='Watch-AAPL', Company__c=aapl.Id, Analyst__c='Sarah Kim', Priority__c='Medium', Reason__c='New product launch — Vision Pro sales data expected', Added_Date__c=Date.today().addDays(-7)),
            new IR_Watchlist__c(Name='Watch-JPM', Company__c=jpm.Id, Analyst__c='David Chen', Priority__c='High', Reason__c='Regulatory review pending — Basel III endgame impact', Added_Date__c=Date.today().addDays(-2)),
            new IR_Watchlist__c(Name='Watch-UNH', Company__c=unh.Id, Analyst__c='Maria Rodriguez', Priority__c='High', Reason__c='Earnings next week — Medicare Advantage enrollment update', Added_Date__c=Date.today().addDays(-1)),
            new IR_Watchlist__c(Name='Watch-XOM', Company__c=xom.Id, Analyst__c='David Chen', Priority__c='Low', Reason__c='Sector rotation play — energy underweight in model portfolio', Added_Date__c=Date.today().addDays(-14)),
            new IR_Watchlist__c(Name='Watch-AMZN', Company__c=amzn.Id, Analyst__c='James Park', Priority__c='Medium', Reason__c='AWS re:Invent announcements — cloud growth reacceleration thesis', Added_Date__c=Date.today().addDays(-5)),
            new IR_Watchlist__c(Name='Watch-CAT', Company__c=cat.Id, Analyst__c='James Park', Priority__c='Medium', Reason__c='Infrastructure bill spending ramp — order backlog catalyst', Added_Date__c=Date.today().addDays(-10)),
            new IR_Watchlist__c(Name='Watch-NEE', Company__c=nee.Id, Analyst__c='Priya Sharma', Priority__c='Low', Reason__c='Interest rate sensitivity — monitoring Fed policy pivot', Added_Date__c=Date.today().addDays(-12))
        };
        insert watchlist;

        List<IR_Research_Note__c> notes = new List<IR_Research_Note__c>{
            new IR_Research_Note__c(Name='NVDA Deep Dive Q1 Preview', Company__c=nvda.Id, Ticker__c='NVDA', Analyst__c='Sarah Kim', Rating__c='Buy', Target_Price__c=180.00, Summary__c='NVIDIA remains our top pick in semiconductors. Data center revenue expected to exceed $26B in Q1.', Full_Brief__c='NVIDIA Corporation continues to dominate the AI accelerator market with estimated 80%+ share of data center GPU shipments. Our DCF model yields fair value of $175-185. Maintain Buy.', Generated_Date__c=DateTime.now().addDays(-3), Data_Sources__c='CRM, Analyst Estimates', Status__c='Published'),
            new IR_Research_Note__c(Name='AAPL Services Momentum', Company__c=aapl.Id, Ticker__c='AAPL', Analyst__c='Sarah Kim', Rating__c='Strong Buy', Target_Price__c=210.00, Summary__c='Apple services revenue continues to inflect higher, now 25% of total revenue at 70%+ gross margins.', Full_Brief__c='Apple Inc reported services revenue of $24.2B in December quarter, up 14% YoY. Installed base exceeds 2.2B devices. Raising target to $210. Strong Buy.', Generated_Date__c=DateTime.now().addDays(-5), Data_Sources__c='CRM, Channel Checks', Status__c='Published'),
            new IR_Research_Note__c(Name='JPM Capital Markets Outlook', Company__c=jpm.Id, Ticker__c='JPM', Analyst__c='David Chen', Rating__c='Buy', Target_Price__c=270.00, Summary__c='JPMorgan well-positioned for capital markets recovery. IB pipeline at multi-year highs.', Full_Brief__c='JPMorgan Chase enters 2026 with strongest IB pipeline in three years. We estimate IB fees grow 20%+ YoY in Q1. Target $270 implies 12x 2026 EPS. Buy.', Generated_Date__c=DateTime.now().addDays(-2), Data_Sources__c='CRM, Regulatory Filings', Status__c='Published'),
            new IR_Research_Note__c(Name='NVDA Earnings Preview Draft', Company__c=nvda.Id, Ticker__c='NVDA', Analyst__c='Priya Sharma', Rating__c='Hold', Target_Price__c=145.00, Summary__c='Current valuation at 35x forward P/E leaves limited margin of safety. Prefer to wait for better entry.', Full_Brief__c='Draft — pending review. Stock fairly valued at current levels. Key concerns: China export restrictions, AMD MI300X competition, potential capex digestion H2 2026. Hold $145.', Generated_Date__c=DateTime.now().addDays(-1), Data_Sources__c='CRM', Status__c='Draft'),
            new IR_Research_Note__c(Name='UNH Medicare Advantage Draft', Company__c=unh.Id, Ticker__c='UNH', Analyst__c='Maria Rodriguez', Rating__c='Strong Buy', Target_Price__c=640.00, Summary__c='UnitedHealth best-positioned managed care company. Optum Health growth accelerating.', Full_Brief__c='Draft — awaiting Q1 enrollment data. Membership grew 4% YoY to 53.4M. Optum revenue per consumer up 12%. Model $420B revenue FY2026. Strong Buy $640.', Generated_Date__c=DateTime.now(), Data_Sources__c='CRM, Enrollment Data', Status__c='Draft')
        };
        insert notes;

        System.debug('Seed data loaded: ' + companies.size() + ' companies, ' + coverages.size() + ' coverage, ' + watchlist.size() + ' watchlist, ' + notes.size() + ' notes');
    }
}
