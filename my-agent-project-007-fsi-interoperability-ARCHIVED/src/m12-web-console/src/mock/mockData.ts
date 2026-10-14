/* ── Dev-mode mock data — NO real MNPI, placeholder names only ── */

import type {
  ChatMessage,
  MeetingPrep,
  PortfolioSummary,
  OrderReview,
  ResearchBrief,
  ReviewItem,
  AuditEntry,
  LayerHealth,
  AdapterHealth,
  PerformanceMetric,
} from "@/api/types";

export const mockChatMessages: ChatMessage[] = [
  {
    id: "msg-001",
    role: "user",
    content: "Prep me for my meeting with Henderson tomorrow",
    timestamp: "2026-04-18T10:32:00Z",
  },
  {
    id: "msg-002",
    role: "agent",
    specialist: "client_service",
    content:
      "Here's your meeting prep for Henderson. I've pulled data from Salesforce FSC, Orion, and eMoney to give you a complete picture.",
    timestamp: "2026-04-18T10:32:15Z",
    sources: [
      { name: "Salesforce FSC", module: "M11" },
      { name: "Orion", module: "M11" },
      { name: "eMoney", module: "M11" },
    ],
    provenanceTraceId: "e2e-001",
    detailType: "meeting_prep",
  },
];

export const mockMeetingPrep: MeetingPrep = {
  clientName: "James Henderson",
  meetingDate: "Apr 19, 2026 2:00 PM",
  advisorName: "Sarah Chen",
  riskProfile: "Moderate",
  objective: "Growth",
  aum: "$1.2M",
  holdings: [
    { symbol: "AAPL", name: "Apple Inc.", allocation: 32, ytdReturn: 12.4, costBasisMethod: "FIFO" },
    { symbol: "VTI", name: "Vanguard Total Stock", allocation: 28, ytdReturn: 8.1, costBasisMethod: "AvgCost" },
    { symbol: "BND", name: "Vanguard Total Bond", allocation: 15, ytdReturn: -1.2, costBasisMethod: "FIFO" },
    { symbol: "MSFT", name: "Microsoft Corp.", allocation: 12, ytdReturn: 15.7, costBasisMethod: "SpecID" },
    { symbol: "CASH", name: "Cash & Equivalents", allocation: 13, ytdReturn: 0, costBasisMethod: "N/A" },
  ],
  talkingPoints: [
    "Portfolio up 9.2% YTD — outperforming benchmark by 1.4%",
    "Rebalance due: equity overweight by 5% vs target allocation",
    "eMoney financial plan on track for retirement goal (2042)",
  ],
  complianceNotes: [
    { status: "pass", text: "No restricted securities in portfolio" },
    { status: "pass", text: "Concentration within firm limits" },
    { status: "warning", text: "Annual review due — last completed 11 months ago" },
  ],
  sources: [
    { name: "Salesforce FSC", module: "M11" },
    { name: "Orion", module: "M11" },
    { name: "eMoney", module: "M11" },
  ],
};

export const mockPortfolio: PortfolioSummary = {
  clientName: "James Henderson",
  totalValue: "$1,200,000",
  ytdReturn: 9.2,
  holdings: mockMeetingPrep.holdings,
  allocation: [
    { category: "US Equity", value: 72, color: "#3b82f6" },
    { category: "Fixed Income", value: 15, color: "#22c55e" },
    { category: "Cash", value: 13, color: "#94a3b8" },
  ],
  performance: [
    { date: "Jan", portfolio: 2.1, benchmark: 1.8 },
    { date: "Feb", portfolio: 3.4, benchmark: 3.1 },
    { date: "Mar", portfolio: 5.8, benchmark: 5.2 },
    { date: "Apr", portfolio: 9.2, benchmark: 7.8 },
  ],
};

export const mockOrderReview: OrderReview = {
  orderId: "ORD-20260418-001",
  side: "BUY",
  symbol: "AAPL",
  securityName: "Apple Inc.",
  quantity: 100,
  orderType: "Limit @ $215.00",
  limitPrice: 215.0,
  account: "Henderson IRA (FID-001)",
  custodian: "Fidelity",
  clientName: "James Henderson",
  riskProfile: "Moderate",
  objective: "Growth",
  currentHolding: { shares: 150, allocation: 32 },
  postTradeHolding: { shares: 250, allocation: 38 },
  complianceChecks: [
    { name: "Suitability", status: "pass", detail: "Growth objective, moderate risk — OK" },
    { name: "Restricted List", status: "pass", detail: "AAPL not restricted" },
    { name: "Concentration", status: "warning", detail: "38% post-trade (limit: 40%)" },
    { name: "Client Scope", status: "pass", detail: "Henderson in advisor scope" },
    { name: "Authority", status: "pass", detail: "order.submit in scope" },
  ],
  estimatedCost: "$21,500.00",
  costBasisMethod: "FIFO",
  taxLotNote: "New lot (no wash sale risk)",
  expiresAt: "2026-04-19T10:32:00Z",
};

export const mockResearchBrief: ResearchBrief = {
  title: "Q1 2026 Market Outlook — Growth Equity Focus",
  summary:
    "US equity markets continue to show strength driven by AI infrastructure spending and resilient consumer demand.",
  sections: [
    {
      heading: "Market Overview",
      content:
        "The S&P 500 gained 7.8% in Q1 2026, led by technology and healthcare sectors. Inflation remains contained at 2.3%.",
      citation: "Bloomberg Terminal, Apr 2026",
    },
    {
      heading: "Portfolio Implications",
      content:
        "Growth-oriented portfolios like Henderson's benefit from current conditions. Consider maintaining equity overweight through Q2.",
      citation: "Orion Analytics",
    },
  ],
  confidenceScore: 0.87,
  sources: [
    { name: "Bloomberg", module: "M11" },
    { name: "Orion", module: "M11" },
  ],
};

export const mockReviewQueue: ReviewItem[] = [
  {
    id: "rev-001",
    advisorName: "Sarah Chen",
    advisorCrd: "1234567",
    clientName: "James Henderson",
    clientId: "CLT-10001",
    type: "Meeting Prep",
    submittedAt: "2026-04-18T09:48:00Z",
    slaDeadline: "2026-04-18T10:30:00Z",
    status: "pending",
    agentOutput:
      "Based on your portfolio review, I recommend increasing your equity allocation by 5% to align with your growth objective. Your current 60/40 split could move to 65/35...",
    opaDecision: "ALLOW",
    opaRule: "authority/main.rego",
    wspSection: "2.0",
    mnpiStripped: ["ssn", "dob"],
    leakageScan: "pass",
    smarchArchive: "pending",
  },
  {
    id: "rev-002",
    advisorName: "Tom Park",
    advisorCrd: "2345678",
    clientName: "Robert Williams",
    clientId: "CLT-10002",
    type: "Portfolio Review",
    submittedAt: "2026-04-18T09:52:00Z",
    slaDeadline: "2026-04-18T11:45:00Z",
    status: "pending",
    agentOutput:
      "Your portfolio has performed well this quarter. The 70/30 equity-bond split remains appropriate for your moderate-aggressive risk profile.",
    opaDecision: "ALLOW",
    opaRule: "authority/main.rego",
    wspSection: "2.0",
    mnpiStripped: ["ssn"],
    leakageScan: "pass",
    smarchArchive: "pending",
  },
  {
    id: "rev-003",
    advisorName: "Lisa Wang",
    advisorCrd: "3456789",
    clientName: "Patricia Davis",
    clientId: "CLT-10003",
    type: "Research Brief",
    submittedAt: "2026-04-18T10:01:00Z",
    slaDeadline: "2026-04-18T13:01:00Z",
    status: "pending",
    agentOutput:
      "Based on current market conditions and your conservative risk profile, I recommend maintaining your current allocation with a slight increase in short-term bonds.",
    opaDecision: "ALLOW",
    opaRule: "authority/main.rego",
    wspSection: "3.1",
    mnpiStripped: ["dob", "tax_id"],
    leakageScan: "pass",
    smarchArchive: "pending",
  },
  {
    id: "rev-004",
    advisorName: "Sarah Chen",
    advisorCrd: "1234567",
    clientName: "Maria Martinez",
    clientId: "CLT-10004",
    type: "Trade Confirm",
    submittedAt: "2026-04-18T10:05:00Z",
    slaDeadline: "2026-04-18T13:05:00Z",
    status: "pending",
    agentOutput:
      "Trade confirmation: Sold 50 shares of TSLA at market price. Proceeds will be reinvested per your rebalancing instructions.",
    opaDecision: "ALLOW",
    opaRule: "authority/main.rego",
    wspSection: "4.2",
    mnpiStripped: ["ssn"],
    leakageScan: "pass",
    smarchArchive: "pending",
  },
  {
    id: "rev-005",
    advisorName: "Tom Park",
    advisorCrd: "2345678",
    clientName: "David Anderson",
    clientId: "CLT-10005",
    type: "Meeting Prep",
    submittedAt: "2026-04-18T10:08:00Z",
    slaDeadline: "2026-04-18T13:53:00Z",
    status: "pending",
    agentOutput:
      "Meeting prep for Anderson: Focus on estate planning updates and the new trust structure. Portfolio is well-positioned for current market conditions.",
    opaDecision: "ALLOW",
    opaRule: "authority/main.rego",
    wspSection: "2.0",
    mnpiStripped: ["ssn", "dob"],
    leakageScan: "pass",
    smarchArchive: "pending",
  },
];

export const mockAuditTrail: AuditEntry[] = [
  {
    id: "aud-001",
    timestamp: "2026-04-18T10:32:00Z",
    traceId: "e2e-001",
    actor: "Sarah Chen",
    action: "client.read",
    target: "Henderson",
    decision: "ALLOW",
    module: "M6",
    sha256: "a3f8c2d1e5b7...",
    provenanceChain: [
      { module: "M1", label: "Identity Verify", sha256: "a3f8c2d1e5b74a89" },
      { module: "M2", label: "Authority Check", sha256: "7b1d4e9f3c2a8b56", rule: "authority/main.rego", wspSection: "2.0" },
      { module: "M4", label: "MNPI Filter", sha256: "9e2f5a8b1c3d7e40" },
      { module: "M6", label: "Route to Vendor", sha256: "1c8b3d5f7a9e2b64" },
      { module: "M11", label: "Salesforce FSC", sha256: "4d7a9f2e8b1c3a56" },
      { module: "M10", label: "Audit Write", sha256: "8f3c1b5d9e7a2f48" },
    ],
    mnpiFilter: { stripped: ["ssn", "dob", "tax_id"], rule: "mnpi/main.rego", archetype: "tier4_ria" },
    wormRecord: "s3://007-worm/2026/04/e2e-001.json",
  },
  {
    id: "aud-002",
    timestamp: "2026-04-18T10:33:00Z",
    traceId: "e2e-002",
    actor: "Agent Exec",
    action: "order.submit",
    target: "AAPL",
    decision: "ESCALATE",
    module: "M6",
    sha256: "b4c9d3e6f7a8...",
  },
  {
    id: "aud-003",
    timestamp: "2026-04-18T10:45:00Z",
    traceId: "e2e-003",
    actor: "Sarah Chen",
    action: "order.approve",
    target: "AAPL",
    decision: "ALLOW",
    module: "M6",
    sha256: "c5d0e4f7a8b9...",
  },
  {
    id: "aud-004",
    timestamp: "2026-04-18T09:15:00Z",
    traceId: "e2e-004",
    actor: "Tom Park",
    action: "client.read",
    target: "Henderson",
    decision: "DENY",
    module: "M6",
    sha256: "d6e1f5a8b9c0...",
  },
];

export const mockSystemHealth: LayerHealth[] = [
  {
    name: "Trust Layer",
    modules: [
      { module: "M1", label: "Identity", status: "healthy", latencyMs: 2 },
      { module: "M2", label: "Policy", status: "healthy", latencyMs: 1 },
      { module: "M6", label: "Gateway", status: "healthy", latencyMs: 8 },
      { module: "M10", label: "Audit", status: "healthy", latencyMs: 5 },
    ],
  },
  {
    name: "Intelligence Layer",
    modules: [
      { module: "M8", label: "Pipeline", status: "healthy", latencyMs: 45 },
      { module: "M9", label: "Router", status: "healthy", latencyMs: 3 },
      { module: "M12", label: "Runtime", status: "healthy", latencyMs: 0 },
    ],
  },
  {
    name: "Data Layer",
    modules: [
      { module: "M3", label: "Schema", status: "healthy", latencyMs: 1 },
      { module: "M7", label: "Translators", status: "degraded", latencyMs: 12 },
      { module: "M11", label: "Adapters", status: "degraded", latencyMs: 25 },
    ],
  },
  {
    name: "Compliance",
    modules: [
      { module: "M2/M4", label: "OPA Engine", status: "healthy", latencyMs: 1 },
      { module: "M5", label: "Config", status: "healthy", latencyMs: 2 },
    ],
  },
];

export const mockAdapters: AdapterHealth[] = [
  { name: "salesforce-fsc", vendor: "Salesforce", protocol: "REST", status: "healthy", circuitBreaker: "CLOSED", lastSuccess: "2m ago" },
  { name: "orion", vendor: "Orion", protocol: "REST", status: "healthy", circuitBreaker: "CLOSED", lastSuccess: "1m ago" },
  { name: "schwab-rest", vendor: "Schwab", protocol: "REST", status: "healthy", circuitBreaker: "CLOSED", lastSuccess: "3m ago" },
  { name: "emoney", vendor: "eMoney", protocol: "REST", status: "degraded", circuitBreaker: "CLOSED", lastSuccess: "5m ago" },
  { name: "fidelity-rest", vendor: "Fidelity", protocol: "REST", status: "down", circuitBreaker: "OPEN", lastSuccess: "2h ago" },
  { name: "bloomberg", vendor: "Bloomberg", protocol: "BLPAPI", status: "healthy", circuitBreaker: "CLOSED", lastSuccess: "30s ago" },
  { name: "factset", vendor: "FactSet", protocol: "MCP", status: "healthy", circuitBreaker: "CLOSED", lastSuccess: "2m ago" },
  { name: "eze-grpc", vendor: "SS&C Eze", protocol: "gRPC", status: "healthy", circuitBreaker: "CLOSED", lastSuccess: "1m ago" },
];

export const mockPerformanceMetrics: PerformanceMetric[] = [
  { service: "M6 Gateway", p50: 8, p95: 22, p99: 45, throughput: "142 req/s" },
  { service: "M2 Policy", p50: 1, p95: 3, p99: 5, throughput: "8,421 evals" },
  { service: "M10 Audit", p50: 5, p95: 12, p99: 18, throughput: "8,421 writes" },
  { service: "Leakage Scan", p50: 2, p95: 6, p99: 9, throughput: "4,210 scans" },
];
