// Test live data actions (Market Data + News via Tavily)
// Run: sf apex run --file scripts/apex/test-live-data.apex
//
// Prerequisites:
//   - DC_MarketDataAction and DC_NewsSearchAction deployed with Tavily API key
//   - Remote Site Setting for api.tavily.com active
//   - Tavily API key set in the Apex classes (replace YOUR_TAVILY_API_KEY)
//
// This script tests both live data actions and reports results.

System.debug('============================================================');
System.debug('  Live Data Test — Market Data + News (Tavily)');
System.debug('============================================================');

Integer passed = 0;
Integer failed = 0;

// ── Test 1: Market Data — S&P 500 ────────────────────────────
try {
    DC_MarketDataAction.MarketInput input1 = new DC_MarketDataAction.MarketInput();
    input1.query = 'S&P 500 today';
    List<DC_MarketDataAction.MarketOutput> results1 = DC_MarketDataAction.getMarketData(
        new List<DC_MarketDataAction.MarketInput>{ input1 }
    );
    String response1 = results1[0].marketSummary;
    if (response1 != null && !response1.contains('Error') && !response1.contains('unavailable')) {
        passed++;
        System.debug('✅ Test 1 PASS: S&P 500 market data');
        System.debug('   Response: ' + response1.substring(0, Math.min(200, response1.length())) + '...');
    } else {
        failed++;
        System.debug('❌ Test 1 FAIL: S&P 500 market data — ' + response1);
    }
} catch (Exception e) {
    failed++;
    System.debug('❌ Test 1 ERROR: ' + e.getMessage());
}

// ── Test 2: Market Data — Apple stock ────────────────────────
try {
    DC_MarketDataAction.MarketInput input2 = new DC_MarketDataAction.MarketInput();
    input2.query = 'Apple AAPL stock price';
    List<DC_MarketDataAction.MarketOutput> results2 = DC_MarketDataAction.getMarketData(
        new List<DC_MarketDataAction.MarketInput>{ input2 }
    );
    String response2 = results2[0].marketSummary;
    if (response2 != null && !response2.contains('Error') && !response2.contains('unavailable')) {
        passed++;
        System.debug('✅ Test 2 PASS: Apple stock data');
        System.debug('   Response: ' + response2.substring(0, Math.min(200, response2.length())) + '...');
    } else {
        failed++;
        System.debug('❌ Test 2 FAIL: Apple stock data — ' + response2);
    }
} catch (Exception e) {
    failed++;
    System.debug('❌ Test 2 ERROR: ' + e.getMessage());
}

// ── Test 3: News — Tesla ─────────────────────────────────────
try {
    DC_NewsSearchAction.NewsInput input3 = new DC_NewsSearchAction.NewsInput();
    input3.query = 'Tesla';
    List<DC_NewsSearchAction.NewsOutput> results3 = DC_NewsSearchAction.searchNews(
        new List<DC_NewsSearchAction.NewsInput>{ input3 }
    );
    String response3 = results3[0].newsSummary;
    if (response3 != null && !response3.contains('Error') && !response3.contains('unavailable')) {
        passed++;
        System.debug('✅ Test 3 PASS: Tesla news');
        System.debug('   Response: ' + response3.substring(0, Math.min(200, response3.length())) + '...');
    } else {
        failed++;
        System.debug('❌ Test 3 FAIL: Tesla news — ' + response3);
    }
} catch (Exception e) {
    failed++;
    System.debug('❌ Test 3 ERROR: ' + e.getMessage());
}

// ── Test 4: News — Federal Reserve ───────────────────────────
try {
    DC_NewsSearchAction.NewsInput input4 = new DC_NewsSearchAction.NewsInput();
    input4.query = 'Federal Reserve interest rates';
    List<DC_NewsSearchAction.NewsOutput> results4 = DC_NewsSearchAction.searchNews(
        new List<DC_NewsSearchAction.NewsInput>{ input4 }
    );
    String response4 = results4[0].newsSummary;
    if (response4 != null && !response4.contains('Error') && !response4.contains('unavailable')) {
        passed++;
        System.debug('✅ Test 4 PASS: Federal Reserve news');
        System.debug('   Response: ' + response4.substring(0, Math.min(200, response4.length())) + '...');
    } else {
        failed++;
        System.debug('❌ Test 4 FAIL: Federal Reserve news — ' + response4);
    }
} catch (Exception e) {
    failed++;
    System.debug('❌ Test 4 ERROR: ' + e.getMessage());
}

System.debug('');
System.debug('============================================================');
System.debug('  Results: ' + passed + ' passed, ' + failed + ' failed');
System.debug('============================================================');
