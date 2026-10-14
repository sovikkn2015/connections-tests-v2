/**
 * REST + reference types matching Pydantic models in openclaw/orchestration/messages.py
 * and the source-chunk / source-table contracts exposed by the API Gateway.
 *
 * Frontend NEVER calls Salesforce directly — only WebSocket to OpenClaw and REST here.
 */

import type { Persona } from './persona';

/** Mirror of openclaw.orchestration.messages.SessionContext (frozen). */
export interface SessionContext {
  session_id: string;
  principal_id: string;
  persona: Persona;
  correlation_id: string;
  parent_brief_id: string | null;
  turn_number: number;
  opened_at: string;
}

export type AgentErrorType = 'timeout' | 'tool_failure' | 'safety' | 'validation';

export interface AgentError {
  agent_id: string;
  error_type: AgentErrorType;
  message: string;
  recoverable: boolean;
  occurred_at: string;
}

export interface Citation {
  span_id: string;
  source_id: string;
  source_type: 'filing' | 'news' | 'market_data' | 'crm' | 'research_brief';
  label: string;
  url?: string;
  page?: number;
  paragraph?: number;
}

export interface ChartIntent {
  chart_type: 'bar' | 'line' | 'pie';
  source_id: string;
  title: string;
  x_label: string;
  y_label: string;
  highlight_segments: string[];
  citation: Citation;
}

export interface SourceTableRow {
  key: string;
  label: string;
  values: Record<string, number>;
}

export interface SourceTable {
  source_id: string;
  title: string;
  columns: string[];
  rows: SourceTableRow[];
  as_of: string;
  citation: Citation;
}

export interface SourceChunk {
  source_id: string;
  title: string;
  filing_type?: string;
  filing_date?: string;
  section?: string;
  page?: number;
  text: string;
  url?: string;
}

export const SEVEN_GATES = [
  'guardrails',
  'mnpi_filter',
  'compliance',
  'hitl',
  'dual_auth',
  'mulesoft',
  'audit',
] as const;

export type GateName = (typeof SEVEN_GATES)[number];

export type GateStatus = 'pending' | 'in_progress' | 'passed' | 'failed' | 'skipped';

export interface GateState {
  name: GateName;
  status: GateStatus;
  started_at?: string;
  completed_at?: string;
  detail?: string;
}

export interface ToolCall {
  span_id: string;
  tool_name: string;
  agent_id: string;
  started_at: string;
  completed_at?: string;
  status: 'running' | 'ok' | 'error';
  latency_ms?: number;
}

export type AdvisorQueueKind = 'inbox' | 'briefs' | 'alerts' | 'pending';

export interface QueueItemSummary {
  id: string;
  kind: AdvisorQueueKind;
  title: string;
  subtitle?: string;
  badge?: string;
  timestamp: string;
  unread?: boolean;
  brief_id?: string;
  client_contact_id?: string;
}

export interface ActionPlan {
  plan_id: string;
  plan_hash: string;
  action_type: 'submit_order' | 'cancel_order' | 'modify_order' | 'initiate_wire';
  summary: string;
  client_household: string;
  notional_usd: number;
  requires_dual_auth: boolean;
  gates: GateState[];
}

export interface SessionWarmRequest {
  persona: Persona;
  ticker_hints?: string[];
}
