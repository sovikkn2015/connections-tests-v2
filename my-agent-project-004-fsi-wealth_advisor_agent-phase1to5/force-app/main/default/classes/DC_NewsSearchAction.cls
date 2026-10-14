/**
 * DC_NewsSearchAction — Searches financial news via Tavily Search API.
 * Returns top headlines with summaries from web search.
 */
public with sharing class DC_NewsSearchAction {

    public class NewsInput {
        @InvocableVariable(label='Query' description='News search query — company, ticker, or topic' required=true)
        public String query;
    }

    public class NewsOutput {
        @InvocableVariable(label='News Summary' description='Top headlines with summaries')
        public String newsSummary;
    }

    // API key placeholder — replace with your Tavily key
    private static final String TAVILY_API_KEY = 'YOUR_TAVILY_API_KEY';

    @InvocableMethod(
        label='Search Financial News'
        description='Search for financial news using Tavily. Returns top 5 headlines with summaries.'
    )
    public static List<NewsOutput> searchNews(List<NewsInput> inputs) {
        List<NewsOutput> outputs = new List<NewsOutput>();

        for (NewsInput input : inputs) {
            NewsOutput output = new NewsOutput();
            try {
                String searchQuery = input.query + ' financial news latest';

                String payload = '{' +
                    '"api_key": "' + TAVILY_API_KEY + '",' +
                    '"query": "' + String.escapeSingleQuotes(searchQuery).replace('"', '\\"') + '",' +
                    '"search_depth": "basic",' +
                    '"include_answer": true,' +
                    '"max_results": 5' +
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
                    output.newsSummary = parseTavilyNewsResponse(input.query, res.getBody());
                } else {
                    output.newsSummary = 'Unable to fetch news (HTTP ' + res.getStatusCode() + '). Please try again.';
                }
            } catch (System.CalloutException ce) {
                output.newsSummary = 'News service temporarily unavailable. Please try again.';
            } catch (Exception e) {
                output.newsSummary = 'Error fetching news. Please try again.';
            }
            outputs.add(output);
        }
        return outputs;
    }

    private static String parseTavilyNewsResponse(String query, String responseBody) {
        Map<String, Object> body = (Map<String, Object>) JSON.deserializeUntyped(responseBody);

        String answer = (String) body.get('answer');
        List<Object> results = (List<Object>) body.get('results');

        String summary = 'Financial News: ' + query + '\n';

        if (String.isNotBlank(answer)) {
            summary += '\n' + answer + '\n';
        }

        if (results != null && !results.isEmpty()) {
            summary += '\nTop Articles:';
            Integer count = 0;
            for (Object resultObj : results) {
                if (count >= 5) break;
                Map<String, Object> result = (Map<String, Object>) resultObj;
                String title = (String) result.get('title');
                String url = (String) result.get('url');
                String content = (String) result.get('content');
                count++;

                summary += '\n\n  ' + count + '. ' + (title != null ? title : 'N/A');
                if (content != null && content.length() > 250) {
                    content = content.substring(0, 250) + '...';
                }
                if (content != null) summary += '\n     ' + content;
            }
        } else {
            summary += '\nNo recent news found for "' + query + '".';
        }

        return summary;
    }
}
