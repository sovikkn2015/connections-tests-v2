/**
 * Dispatches inbound WebSocket events into the brief store and the live
 * traversal store; appends a completed entry to the trace history on
 * `turn_complete`.
 *
 * Two parallel channels flow in: brief_delta (text) and citation (chip metadata).
 * Tool-call spans also arrive here; we update the audit strip. The hook is the
 * single coordinator so components read a consistent merged view.
 */

import { useCallback, useRef } from 'react';
import { useBriefStore } from '../store/brief';
import { useTraversalStore } from '../store/traversal';
import { useTraversalHistoryStore } from '../store/traversalHistory';
import { useSessionStore } from '../store/session';
import { resolveNodeId } from '../data/toolToNode';
import type { InboundMessage } from '../types/agent';

export interface UseStreamingTurnOptions {
  onHitlPrompt?: (ev: Extract<InboundMessage, { type: 'hitl_prompt' }>) => void;
  onError?: (ev: Extract<InboundMessage, { type: 'error' }>) => void;
  onQueueUpdate?: (ev: Extract<InboundMessage, { type: 'queue_update' }>) => void;
  onGate?: (
    ev: Extract<InboundMessage, { type: 'gate_passed' | 'gate_started' | 'gate_failed' }>,
  ) => void;
  /** P1.6: HITL optimistic-approval reconcilers. Called when a gate_passed /
   * gate_failed event with `gate === 'hitl'` arrives. `onOptimisticRollback`
   * receives the tier so the UI can pick the right toast severity. */
  onOptimisticConfirm?: () => void;
  onOptimisticRollback?: (
    message: string,
    tier: 'transient' | 'degraded' | 'recoverable' | 'fatal',
  ) => void;
  /** Optional resolver for the user-visible turn text — used when appending a
   * completed turn to the v1-style history list. If omitted, the history entry
   * is appended with an empty `text`. */
  getTurnText?: (turnId: string) => string | undefined;
}

export function useStreamingTurn(opts: UseStreamingTurnOptions = {}) {
  const optsRef = useRef(opts);
  optsRef.current = opts;

  // Track per-turn gate trace + start time so history rows get a full picture.
  const gateTraceRef = useRef<Array<{ gate: string; status: string; ts: number }>>([]);
  const turnStartRef = useRef<number | null>(null);

  return useCallback((msg: InboundMessage) => {
    const brief = useBriefStore.getState();
    const traversal = useTraversalStore.getState();
    const history = useTraversalHistoryStore.getState();
    const current = optsRef.current;
    switch (msg.type) {
      case 'turn_started':
        brief.startTurn(msg.turn_id);
        traversal.startTurn(msg.turn_id, useSessionStore.getState().persona);
        traversal.markAgentActive(msg.agent_id);
        gateTraceRef.current = [];
        turnStartRef.current = Date.now();
        break;
      case 'brief_delta':
        brief.appendDelta(msg.span_id, msg.delta);
        break;
      case 'citation':
        brief.addCitation(msg.citation);
        break;
      case 'chart_intent':
        brief.addChart(msg.chart);
        break;
      case 'tool_call_start':
        brief.addToolCall(msg.tool);
        traversal.toolCallStart(msg.tool.agent_id, msg.tool.tool_name, msg.tool.span_id);
        break;
      case 'tool_call_end':
        brief.endToolCall(msg.span_id, msg.status, msg.latency_ms);
        traversal.toolCallEnd(
          msg.span_id,
          msg.status,
          msg.latency_ms,
          msg.error?.message,
        );
        break;
      case 'turn_complete': {
        brief.completeTurn({
          costTokens: msg.cost_tokens,
          costUsd: msg.cost_usd,
          durationMs: msg.duration_ms,
        });
        // V3.1 post-hoc gate trace replay. When the backend hasn't streamed
        // live gate events mid-turn, it can ship the canonical trace with
        // turn_complete so the tracker animates on the frontend. Replay at
        // 400ms intervals through the same onGate handler so downstream
        // code sees a normal gate stream.
        if (msg.gate_trace && msg.gate_trace.length > 0 && current.onGate) {
          const traceCopy = msg.gate_trace.slice();
          traceCopy.forEach((g, idx) => {
            setTimeout(() => {
              const synthEv = {
                type: g.status === 'in_progress' ? 'gate_started' : (g.status === 'passed' || g.status === 'skipped' ? 'gate_passed' : 'gate_failed'),
                gate: g.gate,
                status: g.status,
                turn_id: msg.turn_id,
                plan_id: g.plan_id ?? msg.turn_id,
                detail: g.detail,
              } as Extract<InboundMessage, { type: 'gate_passed' | 'gate_started' | 'gate_failed' }>;
              current.onGate?.(synthEv);
              traversal.gateEvent(synthEv.gate, synthEv.status);
            }, idx * 400);
          });
        }
        // Snapshot everything that lit up this turn for the v1-style history row.
        const briefSnap = useBriefStore.getState();
        // mcpsTouched = only MCP-layer node ids, not raw tool names. Resolves
        // via the same toolToNode map the live traversal store uses, so the
        // trace summary row reads "2 tools → market-data, sec-edgar" not
        // "2 tools → get_quote, get_10k".
        const mcps = Array.from(
          new Set(
            briefSnap.toolCalls
              .map((t) => resolveNodeId(t.tool_name))
              .filter(
                (id): id is string => typeof id === 'string' && !id.startsWith('skill:'),
              ),
          ),
        );
        history.appendFromCurrentTurn({
          turnId: msg.turn_id,
          text: current.getTurnText?.(msg.turn_id) ?? '',
          startedAt: turnStartRef.current ?? Date.now() - msg.duration_ms,
          endedAt: Date.now(),
          toolCount: briefSnap.toolCalls.length,
          mcpsTouched: mcps,
          toolCalls: briefSnap.toolCalls,
          gateTrace: gateTraceRef.current.slice(),
          durationMs: msg.duration_ms,
          costUsd: msg.cost_usd,
          costTokens: msg.cost_tokens,
        });
        traversal.completeTurn();
        turnStartRef.current = null;
        break;
      }
      case 'hitl_prompt':
        current.onHitlPrompt?.(msg);
        break;
      case 'gate_passed':
      case 'gate_started':
      case 'gate_failed':
        current.onGate?.(msg);
        traversal.gateEvent(msg.gate, msg.status);
        gateTraceRef.current.push({
          gate: msg.gate,
          status: msg.status,
          ts: Date.now(),
        });
        if (msg.type === 'gate_passed' && msg.gate === 'hitl') {
          current.onOptimisticConfirm?.();
        } else if (msg.type === 'gate_failed') {
          // The server doesn't stamp a four-tier severity on gate_failed yet,
          // so default to `recoverable` - the UI picks the toast accordingly.
          current.onOptimisticRollback?.(
            msg.detail ?? `gate ${msg.gate} failed`,
            'recoverable',
          );
        }
        break;
      case 'error':
        current.onError?.(msg);
        break;
      case 'queue_update':
        current.onQueueUpdate?.(msg);
        break;
      default: {
        const _never: never = msg;
        return _never;
      }
    }
  }, []);
}
