/**
 * Seed data for instant research panel hydration.
 * Focused on the 5 companies with research notes in the SF seed data:
 * NVDA, AAPL, MSFT, JPM, LLY
 */

import type {
  CompanyData,
  CoverageData,
  ConsensusSummary,
  ChartDataPoint,
  FilingData,
  ValuationData,
  SentimentData,
} from '../types';

export const SUPPORTED_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'JPM', 'LLY'] as const;

export function isSupported(ticker: string): boolean {
  return SUPPORTED_TICKERS.includes(ticker.toUpperCase() as typeof SUPPORTED_TICKERS[number]);
}

/* ═══════════════════════════════════════════════════════════════════════════
   1. COMPANY_PROFILES
   ═══════════════════════════════════════════════════════════════════════════ */
export const COMPANY_PROFILES: Record<string, CompanyData> = {
  NVDA: {
    name: 'NVIDIA Corporation', ticker: 'NVDA', sector: 'Technology', exchange: 'NASDAQ',
    marketCap: '$3.30T', peRatio: '65.4', earningsDate: '2026-05-28',
    weekHigh52: '$153.13', weekLow52: '$75.61',
    description: 'NVIDIA designs and sells graphics processing units and system-on-chip units. The company is a dominant force in AI accelerator hardware and data center GPUs.',
    industry: 'Semiconductors', price: 135.40, change: 3.22, changePct: 2.44,
    beta: '1.68', dividendYield: '0.02%', forwardPE: '45.2', profitMargin: '55.8%',
    epsttm: '$2.07', revenuePerShare: '$3.26', movingAvg50: '$128.90', movingAvg200: '$118.45',
  },
  AAPL: {
    name: 'Apple Inc.', ticker: 'AAPL', sector: 'Technology', exchange: 'NASDAQ',
    marketCap: '$3.32T', peRatio: '33.5', earningsDate: '2026-04-30',
    weekHigh52: '$220.20', weekLow52: '$164.08',
    description: 'Apple designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories.',
    industry: 'Consumer Electronics', price: 198.11, change: 1.47, changePct: 0.75,
    beta: '1.24', dividendYield: '0.49%', forwardPE: '30.8', profitMargin: '26.3%',
    epsttm: '$5.91', revenuePerShare: '$24.32', movingAvg50: '$194.55', movingAvg200: '$189.20',
  },
  MSFT: {
    name: 'Microsoft Corporation', ticker: 'MSFT', sector: 'Technology', exchange: 'NASDAQ',
    marketCap: '$3.16T', peRatio: '37.2', earningsDate: '2026-04-22',
    weekHigh52: '$468.35', weekLow52: '$362.90',
    description: 'Microsoft develops and licenses software, services, devices, and solutions worldwide. Its flagship products include Windows, Office 365, Azure cloud, and LinkedIn.',
    industry: 'Software — Infrastructure', price: 425.52, change: 2.18, changePct: 0.51,
    beta: '0.89', dividendYield: '0.72%', forwardPE: '33.1', profitMargin: '35.6%',
    epsttm: '$11.44', revenuePerShare: '$30.72', movingAvg50: '$418.30', movingAvg200: '$405.15',
  },
  JPM: {
    name: 'JPMorgan Chase & Co.', ticker: 'JPM', sector: 'Financials', exchange: 'NYSE',
    marketCap: '$690B', peRatio: '12.4', earningsDate: '2026-04-14',
    weekHigh52: '$271.90', weekLow52: '$189.20',
    description: 'JPMorgan Chase is a global financial services firm and one of the largest banking institutions in the United States.',
    industry: 'Banks — Diversified', price: 243.28, change: -1.12, changePct: -0.46,
    beta: '1.10', dividendYield: '2.05%', forwardPE: '11.8', profitMargin: '33.2%',
    epsttm: '$19.62', revenuePerShare: '$58.10', movingAvg50: '$238.90', movingAvg200: '$225.40',
  },
  LLY: {
    name: 'Eli Lilly and Company', ticker: 'LLY', sector: 'Healthcare', exchange: 'NYSE',
    marketCap: '$820B', peRatio: '78.5', earningsDate: '2026-04-24',
    weekHigh52: '$972.53', weekLow52: '$564.80',
    description: 'Eli Lilly discovers, develops, and markets pharmaceutical products worldwide. Key growth drivers include GLP-1 receptor agonists Mounjaro and Zepbound.',
    industry: 'Drug Manufacturers — General', price: 862.45, change: 8.32, changePct: 0.97,
    beta: '0.42', dividendYield: '0.58%', forwardPE: '52.3', profitMargin: '20.5%',
    epsttm: '$10.99', revenuePerShare: '$42.18', movingAvg50: '$845.20', movingAvg200: '$798.60',
  },
};

/* ═══════════════════════════════════════════════════════════════════════════
   2. ANALYST_COVERAGE
   ═══════════════════════════════════════════════════════════════════════════ */
export const ANALYST_COVERAGE: Record<string, CoverageData[]> = {
  NVDA: [
    { analyst: 'Sarah Kim', firm: 'Goldman Sachs', rating: 'Buy', targetPrice: '$170', lastUpdated: '2026-03-20', lastAction: 'Reiterated' },
    { analyst: 'Priya Sharma', firm: 'Citi', rating: 'Buy', targetPrice: '$160', lastUpdated: '2026-03-14', lastAction: 'Upgraded' },
    { analyst: 'James Park', firm: 'Bank of America', rating: 'Overweight', targetPrice: '$155', lastUpdated: '2026-03-05', lastAction: 'Initiated' },
  ],
  AAPL: [
    { analyst: 'Sarah Kim', firm: 'Goldman Sachs', rating: 'Buy', targetPrice: '$230', lastUpdated: '2026-03-15', lastAction: 'Reiterated' },
    { analyst: 'James Park', firm: 'Bank of America', rating: 'Hold', targetPrice: '$210', lastUpdated: '2026-03-10', lastAction: 'Downgraded' },
    { analyst: 'Priya Sharma', firm: 'Citi', rating: 'Hold', targetPrice: '$205', lastUpdated: '2026-02-28', lastAction: 'Reiterated' },
  ],
  MSFT: [
    { analyst: 'Sarah Kim', firm: 'Goldman Sachs', rating: 'Buy', targetPrice: '$500', lastUpdated: '2026-03-18', lastAction: 'Reiterated' },
    { analyst: 'Priya Sharma', firm: 'Citi', rating: 'Hold', targetPrice: '$450', lastUpdated: '2026-03-12', lastAction: 'Initiated' },
    { analyst: 'Maria Rodriguez', firm: 'JP Morgan', rating: 'Overweight', targetPrice: '$480', lastUpdated: '2026-02-20', lastAction: 'Upgraded' },
  ],
  JPM: [
    { analyst: 'David Chen', firm: 'Morgan Stanley', rating: 'Buy', targetPrice: '$275', lastUpdated: '2026-03-19', lastAction: 'Reiterated' },
    { analyst: 'Maria Rodriguez', firm: 'JP Morgan', rating: 'Overweight', targetPrice: '$265', lastUpdated: '2026-03-06', lastAction: 'Initiated' },
    { analyst: 'James Park', firm: 'Bank of America', rating: 'Hold', targetPrice: '$250', lastUpdated: '2026-02-18', lastAction: 'Reiterated' },
  ],
  LLY: [
    { analyst: 'Maria Rodriguez', firm: 'JP Morgan', rating: 'Buy', targetPrice: '$1050', lastUpdated: '2026-03-22', lastAction: 'Reiterated' },
    { analyst: 'David Chen', firm: 'Morgan Stanley', rating: 'Overweight', targetPrice: '$980', lastUpdated: '2026-03-15', lastAction: 'Upgraded' },
    { analyst: 'Priya Sharma', firm: 'Citi', rating: 'Buy', targetPrice: '$950', lastUpdated: '2026-03-01', lastAction: 'Initiated' },
  ],
};


/* ═══════════════════════════════════════════════════════════════════════════
   3. CONSENSUS_SUMMARIES
   ═══════════════════════════════════════════════════════════════════════════ */
export const CONSENSUS_SUMMARIES: Record<string, ConsensusSummary> = {
  NVDA: { buyCount: 3, holdCount: 0, sellCount: 0, avgTargetPrice: 161.67, highTargetPrice: 170.0, lowTargetPrice: 155.0, currentPrice: 135.40 },
  AAPL: { buyCount: 1, holdCount: 2, sellCount: 0, avgTargetPrice: 215.0, highTargetPrice: 230.0, lowTargetPrice: 205.0, currentPrice: 198.11 },
  MSFT: { buyCount: 2, holdCount: 1, sellCount: 0, avgTargetPrice: 476.67, highTargetPrice: 500.0, lowTargetPrice: 450.0, currentPrice: 425.52 },
  JPM: { buyCount: 2, holdCount: 1, sellCount: 0, avgTargetPrice: 263.33, highTargetPrice: 275.0, lowTargetPrice: 250.0, currentPrice: 243.28 },
  LLY: { buyCount: 3, holdCount: 0, sellCount: 0, avgTargetPrice: 993.33, highTargetPrice: 1050.0, lowTargetPrice: 950.0, currentPrice: 862.45 },
};

/* ═══════════════════════════════════════════════════════════════════════════
   4. CHART_DATA
   ═══════════════════════════════════════════════════════════════════════════ */
export const CHART_DATA: Record<string, ChartDataPoint[]> = {
  NVDA: [
    { date: '2022', revenue: 26.9, eps: 0.17, grossMargin: 56.9, operatingMargin: 20.8, fcf: 3.8 },
    { date: '2023', revenue: 27.0, eps: 0.17, grossMargin: 55.0, operatingMargin: 17.4, fcf: 3.5 },
    { date: '2024', revenue: 60.9, eps: 1.19, grossMargin: 72.7, operatingMargin: 54.1, fcf: 27.0 },
    { date: '2025', revenue: 80.0, eps: 2.07, grossMargin: 74.6, operatingMargin: 62.0, fcf: 40.8 },
  ],
  AAPL: [
    { date: '2022', revenue: 394.3, eps: 6.11, grossMargin: 43.3, operatingMargin: 30.3, fcf: 111.4 },
    { date: '2023', revenue: 383.3, eps: 6.13, grossMargin: 44.1, operatingMargin: 29.8, fcf: 99.6 },
    { date: '2024', revenue: 391.0, eps: 6.42, grossMargin: 45.6, operatingMargin: 31.5, fcf: 105.0 },
    { date: '2025', revenue: 383.0, eps: 5.91, grossMargin: 44.8, operatingMargin: 30.1, fcf: 99.6 },
  ],
  MSFT: [
    { date: '2022', revenue: 198.3, eps: 9.65, grossMargin: 68.4, operatingMargin: 42.1, fcf: 65.1 },
    { date: '2023', revenue: 211.9, eps: 9.68, grossMargin: 68.9, operatingMargin: 41.2, fcf: 59.5 },
    { date: '2024', revenue: 227.6, eps: 11.80, grossMargin: 69.4, operatingMargin: 44.6, fcf: 74.1 },
    { date: '2025', revenue: 228.0, eps: 11.44, grossMargin: 69.8, operatingMargin: 44.2, fcf: 75.2 },
  ],
  JPM: [
    { date: '2022', revenue: 128.7, eps: 12.09, grossMargin: 100.0, operatingMargin: 38.2, fcf: 22.5 },
    { date: '2023', revenue: 154.1, eps: 16.23, grossMargin: 100.0, operatingMargin: 42.8, fcf: 28.1 },
    { date: '2024', revenue: 159.0, eps: 18.22, grossMargin: 100.0, operatingMargin: 44.5, fcf: 30.2 },
    { date: '2025', revenue: 162.0, eps: 19.62, grossMargin: 100.0, operatingMargin: 45.1, fcf: 29.2 },
  ],
  LLY: [
    { date: '2022', revenue: 28.5, eps: 7.94, grossMargin: 76.8, operatingMargin: 28.4, fcf: 5.2 },
    { date: '2023', revenue: 34.1, eps: 5.80, grossMargin: 79.2, operatingMargin: 24.6, fcf: 4.8 },
    { date: '2024', revenue: 45.0, eps: 8.92, grossMargin: 80.5, operatingMargin: 30.2, fcf: 7.1 },
    { date: '2025', revenue: 52.0, eps: 10.99, grossMargin: 81.2, operatingMargin: 32.8, fcf: 9.5 },
  ],
};


/* ═══════════════════════════════════════════════════════════════════════════
   5. SAMPLE_FILINGS
   ═══════════════════════════════════════════════════════════════════════════ */
export const SAMPLE_FILINGS: Record<string, FilingData[]> = {
  NVDA: [
    { type: '10-K', date: '2026-02-26', description: 'Annual Report FY2026', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NVDA&type=10-K', aiSummary: 'NVIDIA reported $80B in revenue, a 31% increase YoY, driven by data center GPU demand. Blackwell architecture shipments exceeded expectations.' },
    { type: '10-Q', date: '2025-11-20', description: 'Quarterly Report Q3 FY2026', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NVDA&type=10-Q', aiSummary: 'Data center revenue reached $19.5B in Q3, up 112% YoY.' },
    { type: '8-K', date: '2026-03-05', description: 'Current Report — Product Launch', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NVDA&type=8-K', aiSummary: 'NVIDIA announced the next-generation Rubin architecture at GTC 2026.' },
  ],
  AAPL: [
    { type: '10-K', date: '2025-10-31', description: 'Annual Report FY2025', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AAPL&type=10-K', aiSummary: 'Apple reported $383B in revenue for FY2025 with services revenue reaching a record $96B.' },
    { type: '10-Q', date: '2026-01-31', description: 'Quarterly Report Q1 FY2026', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AAPL&type=10-Q', aiSummary: 'Q1 FY2026 showed strong iPhone 16 demand with revenue of $102B.' },
    { type: '8-K', date: '2026-02-15', description: 'Current Report — Board Changes', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AAPL&type=8-K', aiSummary: 'Apple announced two new independent directors strengthening AI and healthcare expertise.' },
  ],
  MSFT: [
    { type: '10-K', date: '2025-07-30', description: 'Annual Report FY2025', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=MSFT&type=10-K', aiSummary: 'Microsoft reported $228B in revenue with Azure growing 29% YoY.' },
    { type: '10-Q', date: '2025-10-24', description: 'Quarterly Report Q1 FY2026', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=MSFT&type=10-Q', aiSummary: 'Azure revenue grew 31% with AI services accounting for 12 points of growth.' },
    { type: '8-K', date: '2026-01-10', description: 'Current Report — Acquisition', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=MSFT&type=8-K', aiSummary: 'Microsoft completed a strategic cybersecurity acquisition to bolster Security Copilot.' },
  ],
  JPM: [
    { type: '10-K', date: '2026-02-20', description: 'Annual Report FY2025', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=JPM&type=10-K', aiSummary: 'JPMorgan reported record net income of $56.8B on $162B in revenue.' },
    { type: '10-Q', date: '2025-11-03', description: 'Quarterly Report Q3 FY2025', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=JPM&type=10-Q', aiSummary: 'Net interest income reached $23.4B in Q3 as the rate environment remained favorable.' },
    { type: '8-K', date: '2026-01-14', description: 'Current Report — Earnings Release', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=JPM&type=8-K', aiSummary: 'JPMorgan reported Q4 2025 EPS of $5.12, beating consensus by $0.28.' },
  ],
  LLY: [
    { type: '10-K', date: '2026-02-18', description: 'Annual Report FY2025', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=LLY&type=10-K', aiSummary: 'Eli Lilly reported $52B in revenue driven by Mounjaro and Zepbound. GLP-1 franchise revenue exceeded $28B.' },
    { type: '10-Q', date: '2025-11-05', description: 'Quarterly Report Q3 FY2025', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=LLY&type=10-Q', aiSummary: 'Q3 revenue grew 42% YoY to $14.8B. Mounjaro prescriptions increased 65% sequentially.' },
    { type: '8-K', date: '2026-03-10', description: 'Current Report — FDA Approval', url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=LLY&type=8-K', aiSummary: 'Lilly received FDA approval for orforglipron, the first oral GLP-1 receptor agonist.' },
  ],
};


/* ═══════════════════════════════════════════════════════════════════════════
   6. VALUATION_SNAPSHOTS
   ═══════════════════════════════════════════════════════════════════════════ */
export const VALUATION_SNAPSHOTS: Record<string, ValuationData> = {
  NVDA: {
    dcfFairValue: 158.90, currentPrice: 135.40, upsidePct: 17.4,
    monteCarloMedian: 152.30, monteCarloP5: 88.50, monteCarloP95: 225.80,
    compsRelativeValuation: { peVsPeers: '85% premium to semiconductor peers', evEbitdaVsPeers: '120% premium', psVsPeers: '280% premium to AMD' },
    peers: [
      { ticker: 'AMD', name: 'Advanced Micro Devices', peRatio: 42.8, evEbitda: 32.5, psRatio: 9.8, currentPrice: 158.20 },
      { ticker: 'AVGO', name: 'Broadcom', peRatio: 35.6, evEbitda: 22.4, psRatio: 15.2, currentPrice: 178.50 },
      { ticker: 'INTC', name: 'Intel', peRatio: 108.0, evEbitda: 18.5, psRatio: 2.1, currentPrice: 22.40 },
    ],
    narrative: 'NVIDIA trades at a significant premium to semiconductor peers, reflecting its dominant position in AI accelerators. The DCF model suggests 17.4% upside.',
  },
  AAPL: {
    dcfFairValue: 215.40, currentPrice: 198.11, upsidePct: 8.7,
    monteCarloMedian: 210.50, monteCarloP5: 168.20, monteCarloP95: 258.30,
    compsRelativeValuation: { peVsPeers: '12% premium to tech peers', evEbitdaVsPeers: '8% premium', psVsPeers: '5% discount to MSFT' },
    peers: [
      { ticker: 'MSFT', name: 'Microsoft', peRatio: 37.2, evEbitda: 27.8, psRatio: 13.5, currentPrice: 425.52 },
      { ticker: 'GOOGL', name: 'Alphabet', peRatio: 25.1, evEbitda: 18.7, psRatio: 6.5, currentPrice: 176.49 },
      { ticker: 'SAMSUNG', name: 'Samsung Electronics', peRatio: 15.8, evEbitda: 6.2, psRatio: 1.4, currentPrice: 52.30 },
    ],
    narrative: 'Apple trades at a modest premium to tech peers, justified by its ecosystem lock-in and services growth trajectory.',
  },
  MSFT: {
    dcfFairValue: 468.20, currentPrice: 425.52, upsidePct: 10.0,
    monteCarloMedian: 455.80, monteCarloP5: 375.40, monteCarloP95: 545.60,
    compsRelativeValuation: { peVsPeers: '18% premium to tech peers', evEbitdaVsPeers: '15% premium', psVsPeers: '54% premium to GOOGL' },
    peers: [
      { ticker: 'AAPL', name: 'Apple', peRatio: 33.5, evEbitda: 26.1, psRatio: 8.8, currentPrice: 198.11 },
      { ticker: 'GOOGL', name: 'Alphabet', peRatio: 25.1, evEbitda: 18.7, psRatio: 6.5, currentPrice: 176.49 },
      { ticker: 'CRM', name: 'Salesforce', peRatio: 48.5, evEbitda: 28.3, psRatio: 8.2, currentPrice: 285.40 },
    ],
    narrative: 'Microsoft commands a premium valuation driven by Azure cloud growth and AI monetization via Copilot.',
  },
  JPM: {
    dcfFairValue: 268.40, currentPrice: 243.28, upsidePct: 10.3,
    monteCarloMedian: 260.10, monteCarloP5: 210.50, monteCarloP95: 310.80,
    compsRelativeValuation: { peVsPeers: '5% premium to bank peers', evEbitdaVsPeers: '12% premium', psVsPeers: '18% premium to BAC' },
    peers: [
      { ticker: 'BAC', name: 'Bank of America', peRatio: 11.8, evEbitda: 8.5, psRatio: 3.2, currentPrice: 42.80 },
      { ticker: 'WFC', name: 'Wells Fargo', peRatio: 12.1, evEbitda: 9.2, psRatio: 2.8, currentPrice: 68.50 },
      { ticker: 'GS', name: 'Goldman Sachs', peRatio: 14.5, evEbitda: 10.8, psRatio: 3.5, currentPrice: 520.30 },
    ],
    narrative: 'JPMorgan trades at a slight premium to diversified bank peers, reflecting best-in-class return on equity.',
  },
  LLY: {
    dcfFairValue: 945.80, currentPrice: 862.45, upsidePct: 9.7,
    monteCarloMedian: 920.50, monteCarloP5: 680.20, monteCarloP95: 1180.40,
    compsRelativeValuation: { peVsPeers: '180% premium to pharma peers', evEbitdaVsPeers: '150% premium', psVsPeers: '220% premium to MRK' },
    peers: [
      { ticker: 'NVO', name: 'Novo Nordisk', peRatio: 42.5, evEbitda: 28.8, psRatio: 14.2, currentPrice: 128.50 },
      { ticker: 'MRK', name: 'Merck', peRatio: 14.2, evEbitda: 12.8, psRatio: 4.2, currentPrice: 128.50 },
      { ticker: 'ABBV', name: 'AbbVie', peRatio: 18.5, evEbitda: 14.2, psRatio: 5.8, currentPrice: 185.20 },
    ],
    narrative: 'Eli Lilly trades at a substantial premium to pharma peers, pricing in the massive GLP-1 market opportunity.',
  },
};


/* ═══════════════════════════════════════════════════════════════════════════
   7. SENTIMENT_SNAPSHOTS
   ═══════════════════════════════════════════════════════════════════════════ */
export const SENTIMENT_SNAPSHOTS: Record<string, SentimentData> = {
  NVDA: {
    overallSentiment: 'Bullish', confidence: 'Medium', sentimentScore: 0.58,
    keyDrivers: ['Blackwell GPU demand exceeding supply by 2x', 'Data center revenue growing 100%+ YoY', 'Sovereign AI investments creating new demand vector'],
    transcriptSentiment: 'Jensen Huang described AI infrastructure buildout as a multi-year cycle. Cautious optimism around supply chain normalization.',
    newsSentiment: 'Mixed — strong bullish coverage on AI demand offset by concerns about valuation and potential capex slowdown.',
  },
  AAPL: {
    overallSentiment: 'Bullish', confidence: 'High', sentimentScore: 0.62,
    keyDrivers: ['Services revenue growth accelerating to 15% YoY', 'Apple Intelligence driving iPhone upgrade cycle', 'Share buyback program reducing float by 3% annually'],
    transcriptSentiment: 'Management tone was confident on Q1 call, emphasizing AI integration across product lines.',
    newsSentiment: 'Positive coverage around Apple Intelligence adoption rates and expanding developer ecosystem.',
  },
  MSFT: {
    overallSentiment: 'Bullish', confidence: 'High', sentimentScore: 0.71,
    keyDrivers: ['Azure AI revenue growing triple digits', 'Copilot enterprise adoption exceeding expectations', 'Gaming segment stabilizing post-Activision integration'],
    transcriptSentiment: 'CEO Nadella highlighted AI as a generational platform shift with Azure positioned as the infrastructure layer.',
    newsSentiment: 'Overwhelmingly positive sentiment around Copilot monetization and Azure market share gains.',
  },
  JPM: {
    overallSentiment: 'Bullish', confidence: 'High', sentimentScore: 0.65,
    keyDrivers: ['Record net interest income in elevated rate environment', 'Investment banking recovery gaining momentum', 'Best-in-class credit quality with low charge-off rates'],
    transcriptSentiment: 'Jamie Dimon expressed cautious optimism about the economic outlook while highlighting fortress balance sheet.',
    newsSentiment: 'Positive sentiment driven by strong earnings beats and market share gains in investment banking.',
  },
  LLY: {
    overallSentiment: 'Bullish', confidence: 'High', sentimentScore: 0.78,
    keyDrivers: ['Mounjaro and Zepbound franchise exceeding $28B in revenue', 'Oral GLP-1 (orforglipron) FDA approval expanding TAM', 'Pipeline depth with 15+ Phase III candidates'],
    transcriptSentiment: 'Management expressed high confidence in GLP-1 demand trajectory and manufacturing capacity expansion.',
    newsSentiment: 'Overwhelmingly positive — GLP-1 market expansion narrative dominates coverage with limited bearish counterpoints.',
  },
};
