/**
 * WebSocket wire protocol between frontend and OpenClaw on AgentCore.
 *
 * Outbound: one discriminated union of turn intents.
 * Inbound: one discriminated union of streaming events — brief Markdown on the
 * text channel, citation chips on the citation channel, audit spans on the
 * span channel, gate progress on the gate channel. Stitched by span_id at
 * render time (two parallel streams, one document — narrative §6).
 */

import type {
  ActionPlan,
  AgentError,
  Citation,
  ChartIntent,
  GateName,
  GateStatus,
  ToolCall,
} from './api';

// ============================================================================
// Outbound (frontend -> AgentCore)
// ============================================================================

export interface TurnRequest {
  type: 'turn';
  turn_id: string;
  text: string;
  attachments?: Array<{ kind: 'pdf' | 'image'; url: string }>;
}

export interface HitlApproval {
  type: 'hitl_approval';
  plan_id: string;
  plan_hash: string;
  approved: boolean;
  approver_principal_id: string;
}

export interface PrefetchHint {
  type: 'prefetch';
  tickers: string[];
}

export interface CancelTurn {
  type: 'cancel';
  turn_id: string;
}

export type OutboundMessage = TurnRequest | HitlApproval | PrefetchHint | CancelTurn;

// ============================================================================
// Inbound (AgentCore -> frontend) — discriminated union of event types
// ============================================================================

export interface TurnStartedEvent {
  type: 'turn_started';
  turn_id: string;
  agent_id: string;
  plan_summary?: string;
}

export interface BriefDeltaEvent {
  type: 'brief_delta';
  turn_id: string;
  span_id: string;
  delta: string;
}

export interface CitationEvent {
  type: 'citation';
  turn_id: string;
  citation: Citation;
}

export interface ChartIntentEvent {
  type: 'chart_intent';
  turn_id: string;
  chart: ChartIntent;
}

export interface ToolCallStartEvent {
  type: 'tool_call_start';
  turn_id: string;
  tool: ToolCall;
}

export interface ToolCallEndEvent {
  type: 'tool_call_end';
  turn_id: string;
  span_id: string;
  status: 'ok' | 'error';
  latency_ms: number;
  error?: AgentError;
}

export interface GateEvent {
  type: 'gate_passed' | 'gate_started' | 'gate_failed';
  turn_id: string;
  plan_id: string;
  gate: GateName;
  status: GateStatus;
  detail?: string;
}

export interface HitlPromptEvent {
  type: 'hitl_prompt';
  turn_id: string;
  plan: ActionPlan;
  ttl_seconds: number;
}

export interface TurnCompleteEvent {
  type: 'turn_complete';
  turn_id: string;
  cost_tokens: number;
  cost_usd: number;
  duration_ms: number;
  /** V3.1 post-hoc trace replay for stage-visible tracker animation when
   * backend doesn't stream live gate events. Frontend replays with 400ms
   * spacing through handleGateEvent. */
  gate_trace?: Array<{
    gate: string;
    status: 'in_progress' | 'passed' | 'failed' | 'skipped';
    plan_id?: string;
    detail?: string;
    ts_offset_ms?: number;
  }>;
}

export interface ErrorEvent {
  type: 'error';
  turn_id?: string;
  error: AgentError;
  tier: 'transient' | 'degraded' | 'recoverable' | 'fatal';
}

export interface QueueUpdateEvent {
  type: 'queue_update';
  queue: 'inbox' | 'briefs' | 'alerts' | 'pending';
  item_id: string;
  op: 'add' | 'remove' | 'update';
  /** Full item payload. Present when op is 'add' or 'update'; omitted on
   * 'remove' (item_id alone is enough to evict). The transport should
   * never emit add/update without this — see httpAgentTransport. */
  item?: import('./api').QueueItemSummary;
}

export type InboundMessage =
  | TurnStartedEvent
  | BriefDeltaEvent
  | CitationEvent
  | ChartIntentEvent
  | ToolCallStartEvent
  | ToolCallEndEvent
  | GateEvent
  | HitlPromptEvent
  | TurnCompleteEvent
  | ErrorEvent
  | QueueUpdateEvent;

// ============================================================================
// Connection state machine
// ============================================================================

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed'
  | 'error';
