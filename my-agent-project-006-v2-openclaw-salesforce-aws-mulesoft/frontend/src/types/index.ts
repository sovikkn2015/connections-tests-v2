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

/* ── SEC Filing ── */
export interface FilingData {
  type: string;
  date: string;
  description: string;
  url: string;
  aiSummary?: string;
}

/* ── Pipeline Stage (006-specific) ── */
export interface PipelineStage {
  id: number;
  name: string;
  phase: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'gate';
  startTime?: Date;
  endTime?: Date;
  isHitlGate: boolean;
}

/* ── HITL Gate (006-specific) ── */
export interface HitlGate {
  stageId: number;
  stageName: string;
  context: string;
  options: ('approve' | 'reject' | 'edit' | 'collaborate')[];
  status: 'waiting' | 'approved' | 'rejected';
}

/* ── Tool Event (006-specific — from OpenClaw WebSocket) ── */
export interface ToolEvent {
  id: string;
  name: string;
  phase: 'start' | 'result' | 'error';
  input?: unknown;
  result?: unknown;
  error?: string;
  timestamp: Date;
  duration?: number;
}

/* ── Research Brief (006-specific) ── */
export interface BriefData {
  ticker: string;
  company: string;
  analyst: string;
  rating: string;
  targetPrice: number;
  executiveSummary: string;
  thesis: string;
  catalysts: string;
  risks: string;
  valuation: string;
  generatedDate: string;
  pipelineRunId: string;
}

/* ── Auth State ── */
export interface UserInfo {
  name: string;
  email: string;
  userId: string;
}

/* ── Research Panel Tab (extended from 005) ── */
export type ResearchTab = 'company' | 'coverage' | 'analysis' | 'filings' | 'brief';

/* ── Chart Metric Toggle ── */
export type ChartMetric = 'revenue' | 'margins' | 'eps' | 'fcf';

/* ── Filing Filter ── */
export type FilingFilter = 'All' | '10-K' | '10-Q' | '8-K' | 'DEF 14A';


/* ── MuleSoft HITL events (Phase 6) ──────────────────────────────
 *
 * Canonical WebSocket contract from the OpenClaw Gateway. Every
 * MuleSoft write action (submit_order, rebalance_portfolio,
 * initiate_wire, run_kyc_screening, open_account, close_account)
 * emits `hitl.pending`, then `hitl.completed` once a decision lands.
 *
 * Rule 22: the raw HMAC approval token is NEVER sent to the browser.
 * The frontend only ever sees `token_hash` (sha256 prefix, 16 chars).
 */

export type MuleSoftActionType =
  | 'submit_order'
  | 'initiate_wire'
  | 'rebalance_portfolio'
  | 'run_kyc_screening'
  | 'open_account'
  | 'close_account';

/** Raw envelope pushed over WS when the gateway needs human approval. */
export interface HitlPendingEvent {
  type: 'hitl.pending';
  /** sha256 prefix (first 16 hex chars) of the HMAC approval token */
  token_hash: string;
  /** sha256 of the canonical-JSON action plan the token is bound to */
  plan_hash: string;
  action: MuleSoftActionType;
  /** Human-readable one-liner. Rule 21: allowed in HITL, goes to humans. */
  summary_text: string;
  requires_dual_auth: boolean;
  client_id: string;
  account_id: string;
  /** Unix-time deadline (seconds since epoch). Timeout = abort. */
  expires_at: number;
  /**
   * Action-specific payload for human review (ticker, qty, amount, ...).
   * MAY contain MNPI — rendered only in collapsible viewer, never logged.
   */
  plan_details: Record<string, unknown>;
}

/** Fired when the decision is recorded by the backend (success path). */
export interface HitlCompletedEvent {
  type: 'hitl.completed';
  token_hash: string;
  plan_hash: string;
  decision: 'APPROVED' | 'REJECTED' | 'TIMED_OUT';
  /** MuleSoft reference once the downstream call succeeds (approved path). */
  mulesoft_reference?: string;
  /** Audit log ID from IR_Audit_Log__c once written. */
  audit_log_id?: string;
  reason?: string;
}

/**
 * Local UI state for a pending approval. Kept separate from the raw
 * event so we can layer lifecycle info (awaiting_second, timed_out)
 * without mutating the wire payload.
 */
export interface HitlPendingGate {
  event: HitlPendingEvent;
  status:
    | 'waiting_first'
    | 'awaiting_second'
    | 'approved'
    | 'rejected'
    | 'timed_out'
    | 'error';
  /** Human-readable reason when status is rejected/timed_out/error */
  reason?: string;
  /** MuleSoft reference surfaced after `hitl.completed` */
  mulesoftReference?: string;
  /** Audit log ID surfaced after `hitl.completed` */
  auditLogId?: string;
}
