# Project 006 Run 13 — Targeted Eval Summary

Comparison of 40 previously-failing queries from run11 vs run13 after the BOOTSTRAP-leakage fix.

- Total queries re-run: 40
- **FIXED (FAIL->PASS): 21**
- Regressions (PASS->FAIL): 0
- Still failing: 19
- Already passing (edge cases): 0
- BOOTSTRAP_LEAKAGE flags in judge output: **0**
- Estimated new overall pass rate: ~107/150 = 71.3%  (vs run11 57.3%)

| Q | Lvl | Run11 | Run13 | Delta | Status | Tools | BootstrapFlag |
|---|-----|-------|-------|-------|--------|-------|---------------|
| 3 | L1 | 3.40 | 4.40 | +1.00 | FIXED | market-data | no |
| 4 | L1 | 3.10 | 2.60 | -0.50 | STILL_FAIL | market-data | no |
| 5 | L1 | 3.40 | 3.60 | +0.20 | FIXED | market-data | no |
| 6 | L1 | 3.00 | 3.40 | +0.40 | STILL_FAIL | market-data | no |
| 7 | L1 | 3.10 | 3.60 | +0.50 | FIXED | market-data | no |
| 10 | L1 | 2.30 | 3.10 | +0.80 | STILL_FAIL | market-data | no |
| 12 | L1 | 2.60 | 2.70 | +0.10 | STILL_FAIL | market-data | no |
| 13 | L1 | 2.00 | 1.60 | -0.40 | STILL_FAIL | salesforce-crm | no |
| 14 | L1 | 2.90 | 3.60 | +0.70 | FIXED | salesforce-crm | no |
| 17 | L1 | 3.30 | 3.30 | +0.00 | STILL_FAIL | salesforce-crm | no |
| 21 | L1 | 3.10 | 3.10 | +0.00 | STILL_FAIL | sec-edgar | no |
| 22 | L1 | 2.90 | 3.30 | +0.40 | STILL_FAIL | sec-edgar | no |
| 23 | L1 | 2.40 | 3.30 | +0.90 | STILL_FAIL | sec-edgar | no |
| 25 | L1 | 2.70 | 4.10 | +1.40 | FIXED | market-data,sec-edgar,news-search | no |
| 26 | L1 | 3.40 | 4.10 | +0.70 | FIXED | market-data,news-search | no |
| 27 | L1 | 3.00 | 4.30 | +1.30 | FIXED | sec-edgar,news-search | no |
| 28 | L1 | 2.60 | 4.30 | +1.70 | FIXED | market-data,sec-edgar,news-search | no |
| 29 | L1 | 2.40 | 4.10 | +1.70 | FIXED | sec-edgar,news-search | no |
| 31 | L2 | 3.10 | 4.00 | +0.90 | FIXED | market-data,sec-edgar,news-search | no |
| 32 | L2 | 3.00 | 3.70 | +0.70 | FIXED | market-data,sec-edgar,news-search | no |
| 33 | L2 | 3.10 | 4.00 | +0.90 | FIXED | market-data,sec-edgar,news-search | no |
| 34 | L2 | 2.30 | 2.60 | +0.30 | STILL_FAIL | market-data | no |
| 37 | L2 | 2.40 | 2.60 | +0.20 | STILL_FAIL | market-data,salesforce-crm | no |
| 38 | L2 | 3.40 | 3.90 | +0.50 | FIXED | market-data,salesforce-crm | no |
| 44 | L2 | 3.00 | 2.00 | -1.00 | STILL_FAIL | salesforce-crm | no |
| 45 | L2 | 2.70 | 3.60 | +0.90 | FIXED | market-data,news-search | no |
| 47 | L2 | 3.30 | 3.60 | +0.30 | FIXED | market-data,sec-edgar,news-search | no |
| 48 | L2 | 3.00 | 3.40 | +0.40 | STILL_FAIL | market-data | no |
| 49 | L2 | 3.00 | 2.60 | -0.40 | STILL_FAIL | sec-edgar,salesforce-crm | no |
| 50 | L2 | 3.30 | 2.90 | -0.40 | STILL_FAIL | market-data,sec-edgar | no |
| 51 | L2 | 3.30 | 3.30 | +0.00 | STILL_FAIL | market-data,sec-edgar,news-search | no |
| 52 | L2 | 2.90 | 3.00 | +0.10 | STILL_FAIL | sec-edgar,salesforce-crm | no |
| 53 | L2 | 2.90 | 3.40 | +0.50 | STILL_FAIL | market-data,sec-edgar,news-search | no |
| 54 | L2 | 3.10 | 3.90 | +0.80 | FIXED | sec-edgar,news-search | no |
| 55 | L2 | 3.00 | 3.70 | +0.70 | FIXED | salesforce-crm | no |
| 56 | L2 | 3.40 | 4.10 | +0.70 | FIXED | salesforce-crm | no |
| 57 | L2 | 3.00 | 3.00 | +0.00 | STILL_FAIL | market-data,salesforce-crm | no |
| 58 | L2 | 1.90 | 4.00 | +2.10 | FIXED | salesforce-crm | no |
| 60 | L2 | 2.90 | 4.00 | +1.10 | FIXED | salesforce-crm | no |
| 150 | Edge | 2.90 | 4.40 | +1.50 | FIXED | - | no |

## Still-failing queries (for next iteration)

### Q13 (LL1) avg=1.60
Query: What's on my watchlist?
Flags: ['HALLUCINATED_DATA: Entire watchlist fabricated — no actual Salesforce CRM query was executed', "FABRICATED_SOURCE: Claims 'Source: salesforce-crm' but no SF SOQL skill was invoked", 'NO_GROUND_TRUTH: Cannot verify any watchlist items against real user data', 'FALSE_PRECISION: Specific dates (Mar 1, Mar 5, etc.), priority tiers, and watch theses are entirely invented', 'PERSONA_RISK: ERA persona would rely on this fabricated data as real CRM output, creating operational risk', 'INVESTMENT_CONTEXT: Fabricated watch theses could mislead investment decisions', 'MISSING_TOOL_CALL: Expected SF SOQL skill was not used — response bypassed required data retrieval']
Tools used: ['salesforce-crm']

### Q44 (LL2) avg=2.00
Query: List clients who haven't been contacted in 90+ days
Flags: ['HALLUCINATED_DATA: Client names in Wealth/Family Office and Institutional segments appear fabricated — no ground truth to verify against, but these look generated', 'MIXED_DATA_SOURCES: Commercial/Direct clients appear to be Salesforce sample/demo org data (e.g., Edge Communications, GenePoint, sForce) mixed with fabricated FSI-specific names', 'LOGIC_ERROR: Claims 38 records but Wealth table has 15 rows, Institutional has 10, Commercial has 12 — totals to 37, not 38', 'METHODOLOGY_FLAW: Query appears to return accounts with null LastActivityDate rather than accounts with LastActivityDate < 90 days ago — these are different conditions', 'NULL_LASTACTIVITYDATE_MISINTERPRETATION: Null LastActivityDate does not necessarily mean 90+ days without contact; it may mean activity tracking was never enabled or data was not migrated', 'PII_EXPOSURE: Phone numbers for real-looking commercial entities are included without necessity', 'UNVERIFIABLE_CLAIMS: No SOQL query shown to validate the methodology or results', 'DEMO_ORG_DATA: Several accounts (United Oil & Gas, GenePoint, sForce) are recognizable Salesforce demo org fixtures, suggesting this may be a sandbox environment response presented as production data']
Tools used: ['salesforce-crm']

### Q4 (LL1) avg=2.60
Query: What's the S&P 500 at?
Flags: ['SELF_CONTRADICTION: Agent initially states 5,893.62 then corrects to 7,119.18 — both figures presented as factual, undermining credibility', 'POTENTIAL_HALLUCINATION: No ground truth available to verify 7,119.18 figure; the initial blurted figure 5,893.62 suggests model confusion or fabrication', 'DATA_RELIABILITY: Two conflicting S&P 500 values in a single response is a critical error for a PM persona relying on accurate market data', 'UNVERIFIABLE_PRECISION: Specific figures like 7,119.18 and volume of 1.27B cannot be verified against ground truth', 'TOOL_USAGE_AMBIGUITY: Unclear if Market Data MCP was actually called or if figures were hallucinated']
Tools used: ['market-data']

### Q34 (LL2) avg=2.60
Query: How has GOOGL stock reacted to the last 4 earnings?
Flags: ['FABRICATED_DATA: Q2 2025, Q3 2025, Q4 2025, and Q2 2026 earnings dates and prices are entirely fabricated — these dates are in the future relative to any reasonable knowledge cutoff or are speculative', 'HALLUCINATED_FUTURE_EVENTS: The agent invents earnings reactions for quarters that have not yet occurred (Q2 2025 onward if evaluated near early 2025, or all four if the agent lacks real-time data)', 'SPECULATIVE_PRICE_DATA: Specific price levels like $195.75, $267.47, $333.04 appear invented with false precision', 'NO_TOOL_USE_CONFIRMED: The agent claims to use Market Data MCP but presents fabricated future data inconsistent with any verified source', 'MISLEADING_CONFIDENCE: Presents hallucinated data in a structured table with high confidence, which is dangerous for financial decision-making', "DISCLAIMER_INSUFFICIENT: The caveat about 'estimated' dates is buried and does not adequately warn that the data may be entirely fabricated", 'NEXT_EARNINGS_SPECULATION: Providing a specific EPS consensus estimate of $2.85 for Q2 2026 without verified sourcing is hallucination risk']
Tools used: ['market-data']

### Q37 (LL2) avg=2.60
Query: What's on my watchlist that reports this week and has moved more than 5%?
Flags: ['FABRICATED_DATA: All specific price figures appear hallucinated — no ground truth to validate against, and the agent presents precise numbers (e.g., GOOGL $332.29→$336.96, TSLA $386.42→$389.67) with false confidence', "DATE_INCONSISTENCY: Response header states 'July 21–25, 2026' but source note says 'as of Apr 22, 2026' — internally contradictory timestamps", "CONFLICTING_CONCLUSIONS: The 5-day analysis says neither stock moved >5%, but the agent then presents both as actionable 'standouts' using a self-selected 10-day window — goal-post shifting to force a positive result", "UNVERIFIED_WATCHLIST: Claims '20 CRM watchlist names' and lists 20 specific tickers but there is no ground truth to confirm these are the user's actual watchlist", 'EPS_AND_REVENUE_ESTIMATES_UNVERIFIED: Specific consensus figures ($2.85 EPS for GOOGL, $0.45 for TSLA, revenue estimates) are presented with no verifiable sourcing', "SELF_CONTRADICTORY_ANSWER: The direct answer to 'moved more than 5%?' is technically 'neither' on the 5-day window, yet the response buries this and pivots to a 10-day window without user request", "SOURCE_CITATIONS_NOT_TRACEABLE: 'market-data/Finnhub + Yahoo Finance' cited generically without query specifics, timestamps, or retrievable endpoints"]
Tools used: ['market-data', 'salesforce-crm']

### Q49 (LL2) avg=2.60
Query: Compare insider buying across my coverage universe this quarter
Flags: ["FABRICATED_DATA: Specific filing counts, dates, and clustering patterns (e.g., 'CRM 5 filings all on Mar 24', 'CVX cluster Mar 4', 'JPM 5 filings Apr 15') appear fabricated — no ground truth to verify and agent acknowledges it cannot classify buy vs. sell without XML parsing", 'HALLUCINATED_SPECIFICITY: Precise filing counts per ticker (0–5) presented with false confidence when agent admits data limitations', "METHODOLOGY_MISMATCH: Agent explicitly states it cannot distinguish buys from sells without XML parsing, yet the query is specifically about 'insider buying' — the core question goes unanswered", 'UNVERIFIABLE_COVERAGE_UNIVERSE: The 30 companies, 3 analysts, and analyst assignments (Chen, Rodriguez, Sharma) are asserted without confirmed SOQL retrieval shown', "POTENTIAL_MNPI_RISK: Presenting unverified insider transaction patterns as 'signals' (e.g., TSLA Underweight + insider buys as 'contrarian signal') without verification could be misleading", "SOURCE_ATTRIBUTION_WEAK: Claims 'salesforce-crm (coverage/ratings), sec-edgar Form 4 filings' but no accession numbers, CIK references, or verifiable provenance provided", 'CONFLATION: Filing activity volume ≠ insider buying — the agent substitutes a proxy metric for the actual requested metric without adequately flagging this substitution upfront']
Tools used: ['sec-edgar', 'salesforce-crm']

### Q12 (LL1) avg=2.70
Query: When does JPMorgan report earnings?
Flags: ['DATE UNVERIFIABLE: July 13, 2026 cannot be confirmed — JPMorgan typically reports Q2 earnings in mid-July, but this specific 2026 date is a forward projection that may be fabricated or hallucinated', 'EPS ESTIMATE UNVERIFIABLE: $5.46 EPS estimate cannot be cross-checked against ground truth; likely hallucinated analyst consensus', 'REVENUE ESTIMATE UNVERIFIABLE: ~$49.4B revenue estimate cannot be verified and may be fabricated', "WRONG TOOL USED: Query expected SF skill (SOQL) per persona ERA; agent cited 'market-data, earnings calendar lookup' — no SOQL query evidence", 'REPORT HOUR NOT SPECIFIED: Incomplete — pre-market vs post-market matters for trading decisions', "SOURCE VAGUE: 'market-data, earnings calendar lookup' is not a traceable or auditable source"]
Tools used: ['market-data']

### Q50 (LL2) avg=2.90
Query: Any insider trading at Microsoft recently and what's the stock done since?
Flags: ['LIKELY_HALLUCINATED_DATA: Specific accession numbers, exact prices, volume figures, and dates cannot be verified against ground truth — high risk of fabrication', 'MNPI_CONCERN: Agent claims to withhold MNPI-sensitive fields but then provides granular insider filing dates and accession numbers that may be fabricated', 'FABRICATED_SPECIFICITY: Exact price points like $431.64, $555.45, $356.28, and volume of 128M shares appear suspiciously precise without verifiable sourcing', "MISLEADING_ATTRIBUTION: Claims sources are 'sec-edgar MCP & market-data (Yahoo Finance)' but accession numbers for future dates (2026) cannot be independently verified", "SPECULATIVE_ANALYSIS: Commentary suggesting insider filings 'coincided with stock near multi-month lows' implies directional trading signal without basis", 'DATE_ANOMALY: All dates reference 2026, which is a future year relative to most training data — raises questions about data provenance', 'INCOMPLETE_FORM4_DATA: No actual transaction details provided (buyer/seller name, shares, price, transaction type) which are the core of Form 4 usefulness']
Tools used: ['market-data', 'sec-edgar']

### Q52 (LL2) avg=3.00
Query: Show me all 10-K filings from my watchlist companies in the last 30 days
Flags: ['FABRICATED_DATA: All accession numbers, filing dates, and direct EDGAR URLs appear to be hallucinated — no ground truth available but specific accession numbers like 0000104169-26-000055 cannot be verified and are highly likely fabricated', 'HALLUCINATED_URLS: Direct links to SEC EDGAR filings are constructed URLs that may not resolve to real documents', "TEMPORAL_INCONSISTENCY: Agent claims to know 'today is approximately mid-March 2026' by inferring from a filing date, which is circular reasoning and unverifiable", 'FABRICATED_SPECIFICITY: Precise filing dates for all 20 companies presented with false confidence — no real EDGAR query output shown', 'TOOL_OUTPUT_NOT_SHOWN: Agent claims to have pulled live data from SEC EDGAR MCP and Salesforce but shows no actual tool call results or raw API responses', 'MIXED_REAL_FAKE: Company names and tickers appear legitimate but all associated metadata is likely fabricated', 'SAFETY_CONCERN: Presenting fabricated financial filing data as authoritative could lead to incorrect investment research decisions']
Tools used: ['sec-edgar', 'salesforce-crm']

### Q57 (LL2) avg=3.00
Query: Any MNPI flags on stocks reporting this week?
Flags: ['Earnings estimates (EPS, revenue) appear fabricated — no ground truth available to verify, and these are presented with false precision as if sourced from a live calendar', "Date 'Week of July 21, 2026' is a future date, making all earnings data speculative or hallucinated", 'No SOQL queries shown — expected tool usage (SF skill with SOQL) is not evidenced in the response', 'MNPI flags not found in CRM, but the agent pivots to presenting unverified market data, which could itself be MNPI-adjacent if acted upon', 'The agent provides structural CRM recommendations (field names, schema suggestions) that were not requested and may be outside scope for a CO persona', "Source attribution is vague — 'market-data, earnings calendar' cited without specific provider or query trace", 'No actual SOQL query results displayed, reducing traceability and auditability']
Tools used: ['market-data', 'salesforce-crm']

