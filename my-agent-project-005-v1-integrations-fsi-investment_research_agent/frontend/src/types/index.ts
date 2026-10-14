/* ── Chat Messages ── */
export interface Message {
  id: string;
  role: 'user' | 'agent';
  text: string;
  timestamp: Date;
  isStreaming?: boolean;
}

/* ── Company Data ── */
export interface CompanyData {
  name: string;
  ticker: string;
  sector: string;
  exchange: string;
  marketCap: string;
  peRatio: string;
  earningsDate: string;
  weekHigh52: string;
  weekLow52: string;
  description: string;
  /* v2 fields */
  industry: string;
  price: number;
  change: number;
  changePct: number;
  beta: string;
  dividendYield: string;
  forwardPE: string;
  profitMargin: string;
  epsttm: string;
  revenuePerShare: string;
  movingAvg50: string;
  movingAvg200: string;
}

/* ── Analyst Coverage ── */
export interface CoverageData {
  analyst: string;
  firm: string;
  rating: 'Buy' | 'Hold' | 'Sell' | 'Overweight' | 'Underweight';
  targetPrice: string;
  lastUpdated: string;
  lastAction?: 'Initiated' | 'Reiterated' | 'Upgraded' | 'Downgraded';
}

/* ── Consensus Summary ── */
export interface ConsensusSummary {
  buyCount: number;
  holdCount: number;
  sellCount: number;
  avgTargetPrice: number;
  highTargetPrice: number;
  lowTargetPrice: number;
  currentPrice: number;
}

/* ── Financial Chart Point ── */
export interface ChartDataPoint {
  date: string;
  revenue: number;
  eps: number;
  price?: number;
  grossMargin?: number;
  operatingMargin?: number;
  fcf?: number;
}


/* ── Valuation Data ── */
export interface ValuationData {
  dcfFairValue: number;
  currentPrice: number;
  upsidePct: number;
  monteCarloMedian: number;
  monteCarloP5: number;
  monteCarloP95: number;
  compsRelativeValuation: {
    peVsPeers: string;
    evEbitdaVsPeers: string;
    psVsPeers: string;
  };
  peers: {
    ticker: string;
    name: string;
    peRatio: number;
    evEbitda: number;
    psRatio: number;
    currentPrice: number;
  }[];
  narrative: string;
}

/* ── Sentiment Data ── */
export interface SentimentData {
  overallSentiment: 'Bullish' | 'Neutral' | 'Bearish';
  confidence: 'High' | 'Medium' | 'Low';
  sentimentScore: number;
  keyDrivers: string[];
  transcriptSentiment: string;
  newsSentiment: string;
}

/* ── Financial Statement Row ── */
export interface FinancialStatement {
  year: string;
  revenueBn: number;
  netIncomeBn: number;
  epsDiluted: number;
  grossMarginPct: number;
  operatingMarginPct: number;
  fcfBn: number;
}

/* ── SEC Filing (enhanced) ── */
export interface FilingData {
  type: string;
  date: string;
  description: string;
  url: string;
  aiSummary?: string;
}

/* ── Agent Session ── */
export interface AgentSession {
  sessionId: string;
  sequenceId: number;
}

/* ── Research Panel Tab ── */
export type ResearchTab = 'company' | 'coverage' | 'analysis' | 'filings';

/* ── Chart Metric Toggle ── */
export type ChartMetric = 'revenue' | 'margins' | 'eps' | 'fcf';

/* ── Filing Filter ── */
export type FilingFilter = 'All' | '10-K' | '10-Q' | '8-K' | 'DEF 14A';

/* ── Auth State ── */
export interface AuthState {
  accessToken: string | null;
  instanceUrl: string | null;
  userInfo: UserInfo | null;
}

export interface UserInfo {
  name: string;
  email: string;
  userId: string;
}
