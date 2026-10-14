/**
 * DC_MarketDataAction — Fetches market data via Tavily Search API.
 * Tavily does web search + content extraction in one call.
 * API key is set via Custom Metadata or hardcoded for demo.
 */
public with sharing class DC_MarketDataAction {

    public class MarketInput {
        @InvocableVariable(label='Query' description='Market data query — ticker, index, or company name' required=true)
        public String query;
    }

    public class MarketOutput {
        @InvocableVariable(label='Market Summary' description='Market data from web search')
        public String marketSummary;
    }

    // API key placeholder — replace with your Tavily key
    // In production, use Custom Metadata or Named Credential
    private static final String TAVILY_API_KEY = 'YOUR_TAVILY_API_KEY';

    @InvocableMethod(
        label='Get Market Data'
        description='Search the web for real-time market data using Tavily. Supports tickers, indices, and company names.'
    )
    public static List<MarketOutput> getMarketData(List<MarketInput> inputs) {
        List<MarketOutput> outputs = new List<MarketOutput>();

        for (MarketInput input : inputs) {
            MarketOutput output = new MarketOutput();
            try {
                String searchQuery = input.query + ' stock price today market data';

                String payload = '{' +
                    '"api_key": "' + TAVILY_API_KEY + '",' +
                    '"query": "' + String.escapeSingleQuotes(searchQuery).replace('"', '\\"') + '",' +
                    '"search_depth": "basic",' +
                    '"include_answer": true,' +
                    '"max_results": 3' +
                '}';

                HttpRequest req = new HttpRequest();
                req.setEndpoint('https://api.tavily.com/search');
                req.setMethod('POST');
                req.setHeader('Content-Type', 'application/json');
                req.setBody(payload);
                req.setTimeout(15000);

                Http http = new Http();
                HttpResponse res = http.send(req);

                if (res.getStatusCode() == 200) {
                    output.marketSummary = parseTavilyResponse(input.query, res.getBody());
                } else {
                    output.marketSummary = 'Unable to fetch market data (HTTP ' + res.getStatusCode() + '). Please try again.';
                }
            } catch (System.CalloutException ce) {
                output.marketSummary = 'Market data service temporarily unavailable. Please try again.';
            } catch (Exception e) {
                output.marketSummary = 'Error fetching market data. Please try again.';
            }
            outputs.add(output);
        }
        return outputs;
    }

    private static String parseTavilyResponse(String query, String responseBody) {
        Map<String, Object> body = (Map<String, Object>) JSON.deserializeUntyped(responseBody);

        String answer = (String) body.get('answer');
        List<Object> results = (List<Object>) body.get('results');

        String summary = 'Market Data: ' + query + '\n';

        if (String.isNotBlank(answer)) {
            summary += '\n' + answer + '\n';
        }

        if (results != null && !results.isEmpty()) {
            summary += '\nSources:';
            Integer count = 0;
            for (Object resultObj : results) {
                if (count >= 3) break;
                Map<String, Object> result = (Map<String, Object>) resultObj;
                String title = (String) result.get('title');
                String url = (String) result.get('url');
                String content = (String) result.get('content');
                count++;

                summary += '\n  ' + count + '. ' + (title != null ? title : 'N/A');
                if (content != null && content.length() > 200) {
                    content = content.substring(0, 200) + '...';
                }
                if (content != null) summary += '\n     ' + content;
            }
        }

        return summary;
    }
}
