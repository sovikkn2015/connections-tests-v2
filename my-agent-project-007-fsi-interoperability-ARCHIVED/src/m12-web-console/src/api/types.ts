/* ── API Request / Response types — M6 Gateway communication ── */

export type UserRole = "advisor" | "principal" | "compliance_officer" | "admin";
export type FirmArchetype = "tier3_bd" | "tier4_ria" | "tier2_hybrid" | "tier5_family_office";

export interface AIDClaims {
  sub: string;
  name: string;
  role: UserRole;
  firm_id: string;
  firm_archetype: FirmArchetype;
  crd_number?: string;
  scopes: string[];
}

/* ── Chat ── */

export type MessageRole = "user" | "agent" | "system" | "hitl";
export type SpecialistType = "client_service" | "research" | "execution" | "onboarding" | "compliance";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  specialist?: SpecialistType;
  content: string;
  timestamp: string;
  sources?: DataSource[];
  provenanceTraceId?: string;
  hitlAction?: HITLAction;
  detailType?: DetailType;
  detailPayload?: unknown;
}

export interface DataSource {
  name: string;
  module: string;
}

export interface HITLAction {
  type: "order_approval" | "principal_review" | "edit_confirm";
  actionId: string;
  status: "pending" | "approved" | "rejected" | "expired";
  expiresAt?: string;
}

export type DetailType = "meeting_prep" | "portfolio" | "order_review" | "research_brief" | "empty";

export interface SendMessageRequest {
  content: string;
  conversationId?: string;
}

export interface SSEEvent {
  type: "token" | "detail" | "done" | "error" | "blocked";
  data: string;
}

/* ── Meeting Prep ── */

export interface MeetingPrep {
  clientName: string;
  meetingDate: string;
  advisorName: string;
  riskProfile: string;
  objective: string;
  aum: string;
  holdings: Holding[];
  talkingPoints: string[];
  complianceNotes: ComplianceNote[];
  sources: DataSource[];
}

export interface Holding {
  symbol: string;
  name: string;
  allocation: number;
  ytdReturn: number;
  costBasisMethod: string;
}

export interface ComplianceNote {
  status: "pass" | "warning" | "fail";
  text: string;
}

/* ── Portfolio ── */

export interface PortfolioSummary {
  clientName: string;
  totalValue: string;
  ytdReturn: number;
  holdings: Holding[];
  allocation: AllocationSlice[];
  performance: PerformancePoint[];
}

export interface AllocationSlice {
  category: string;
  value: number;
  color: string;
}

export interface PerformancePoint {
  date: string;
  portfolio: number;
  benchmark: number;
}

/* ── Order Review ── */

export interface OrderReview {
  orderId: string;
  side: "BUY" | "SELL";
  symbol: string;
  securityName: string;
  quantity: number;
  orderType: string;
  limitPrice?: number;
  account: string;
  custodian: string;
  clientName: string;
  riskProfile: string;
  objective: string;
  currentHolding: { shares: number; allocation: number };
  postTradeHolding: { shares: number; allocation: number };
  complianceChecks: ComplianceCheck[];
  estimatedCost: string;
  costBasisMethod: string;
  taxLotNote: string;
  expiresAt: string;
}

export interface ComplianceCheck {
  name: string;
  status: "pass" | "warning" | "fail";
  detail: string;
}

/* ── Research Brief ── */

export interface ResearchBrief {
  title: string;
  summary: string;
  sections: { heading: string; content: string; citation?: string }[];
  confidenceScore: number;
  sources: DataSource[];
}

/* ── Principal Review Queue ── */

export type ReviewStatus = "pending" | "approved" | "rejected" | "edited";

export interface ReviewItem {
  id: string;
  advisorName: string;
  advisorCrd: string;
  clientName: string;
  clientId: string;
  type: string;
  submittedAt: string;
  slaDeadline: string;
  status: ReviewStatus;
  agentOutput: string;
  opaDecision: string;
  opaRule: string;
  wspSection: string;
  mnpiStripped: string[];
  leakageScan: "pass" | "fail";
  smarchArchive: "pending" | "archived";
}

export interface ReviewAction {
  reviewId: string;
  action: "approve" | "reject" | "edit_approve";
  reason?: string;
  editedContent?: string;
}

/* ── Audit Trail ── */

export type AuditDecision = "ALLOW" | "DENY" | "ESCALATE" | "BLOCK";

export interface AuditEntry {
  id: string;
  timestamp: string;
  traceId: string;
  actor: string;
  action: string;
  target: string;
  decision: AuditDecision;
  module: string;
  sha256: string;
  provenanceChain?: ProvenanceStage[];
  mnpiFilter?: { stripped: string[]; rule: string; archetype: string };
  wormRecord?: string;
}

export interface ProvenanceStage {
  module: string;
  label: string;
  sha256: string;
  rule?: string;
  wspSection?: string;
}

export interface AuditFilters {
  dateFrom?: string;
  dateTo?: string;
  client?: string;
  advisor?: string;
  action?: string;
  decision?: AuditDecision;
}

/* ── System Health ── */

export type HealthStatus = "healthy" | "degraded" | "down" | "unknown";
export type CircuitBreakerState = "CLOSED" | "OPEN" | "HALF_OPEN";

export interface ModuleHealth {
  module: string;
  label: string;
  status: HealthStatus;
  latencyMs: number;
}

export interface LayerHealth {
  name: string;
  modules: ModuleHealth[];
}

export interface AdapterHealth {
  name: string;
  vendor: string;
  protocol: string;
  status: HealthStatus;
  circuitBreaker: CircuitBreakerState;
  lastSuccess: string;
}

export interface PerformanceMetric {
  service: string;
  p50: number;
  p95: number;
  p99: number;
  throughput: string;
}
