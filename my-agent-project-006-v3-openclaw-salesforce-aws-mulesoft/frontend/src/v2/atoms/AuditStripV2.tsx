/**
 * v2 Audit strip — trace id, WS state, per-specialist pills, HITL-hold
 * indicator when a plan is pending, right-aligned summary (spans · duration
 * · cost · Langfuse).
 *
 * Wired:
 *   - correlation id, WS state: useSessionStore
 *   - tool-call pills: useBriefStore.toolCalls (live, from WS tool_call_*)
 *   - HITL hold: GateState[] prop (advisor only; pass null to disable)
 */

import { useMemo } from 'react';
import { useBriefStore } from '../../shared/store/brief';
import { useSessionStore } from '../../shared/store/session';
import type { GateState } from '../../shared/types/api';

export interface AuditStripV2Props {
  /** Optional gate state for the HITL-hold indicator. Advisor passes it; other personas omit. */
  gates?: GateState[] | null;
  /** Langfuse base URL — when present, renders the ⌥L link. */
  langfuseBaseUrl?: string;
  /** Persona-bar color for the trace-id label. Defaults to brand blue. */
  traceColor?: string;
}

function shortSpec(toolName: string): string {
  // Collapse long tool names to a pill-sized chip. "get_quote" -> "get_quote",
  // "search_financial_news" -> "search_news".
  if (toolName.length <= 22) return toolName;
  return toolName.slice(0, 20) + '…';
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatUsd(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

export function AuditStripV2({ gates, langfuseBaseUrl, traceColor = '#1B96FF' }: AuditStripV2Props) {
  const correlationId = useSessionStore((s) => s.correlationId);
  const connectionStatus = useSessionStore((s) => s.connectionStatus);
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const costUsd = useBriefStore((s) => s.costUsd);
  const durationMs = useBriefStore((s) => s.durationMs);

  // Collapse pills to one per unique agent_id (the uploaded design shows
  // "market-spec [ok]" not "market_specialist · get_quote [ok]").
  const pills = useMemo(() => {
    type Pill = { key: string; status: 'running' | 'ok' | 'error' };
    const byAgent = new Map<string, Pill>();
    for (const tc of toolCalls) {
      const existing = byAgent.get(tc.agent_id);
      // Escalation: error > running > ok (we want the most-serious to show).
      let next: Pill['status'] = tc.status;
      if (existing) {
        if (existing.status === 'error') next = 'error';
        else if (existing.status === 'running' && tc.status !== 'error') next = 'running';
        else next = existing.status;
        if (tc.status === 'error') next = 'error';
      }
      byAgent.set(tc.agent_id, { key: tc.agent_id, status: next });
    }
    return Array.from(byAgent.values());
  }, [toolCalls]);

  // HITL hold: check if any gate is in_progress AND named 'hitl'.
  const hitlHold = (gates ?? []).find((g) => g.name === 'hitl' && g.status === 'in_progress');
  const hitlHoldSince = hitlHold?.started_at ? Date.parse(hitlHold.started_at) : null;
  const hitlDurationMs = hitlHoldSince ? Date.now() - hitlHoldSince : 0;

  const spanCount = toolCalls.length;

  return (
    <div className="v2-audit-strip" role="status" aria-label="Audit trace">
      <span className="v2-audit-strip__muted">trace</span>
      <span style={{ color: traceColor }} title="Langfuse trace id">
        {correlationId?.slice(0, 13) ?? '—'}
      </span>
      <span className="v2-audit-strip__muted">·</span>
      <span className="live-dot" data-status={connectionStatus}>
        ws: {connectionStatus}
      </span>
      {hitlHold && (
        <>
          <span className="v2-audit-strip__muted">·</span>
          <span className="v2-audit-strip__hitl">
            ⏸ HITL hold · gate ④
            {hitlDurationMs > 0 && ` · ${formatMs(hitlDurationMs)}`}
          </span>
        </>
      )}
      <span className="v2-audit-strip__muted">·</span>
      {pills.length === 0 ? (
        <span className="v2-audit-strip__muted">no active spans</span>
      ) : (
        pills.map((p) => (
          <span key={p.key} className="v2-audit-strip__pill" data-status={p.status}>
            {shortSpec(p.key)}
            <span className="v2-audit-strip__pill-status">{p.status}</span>
          </span>
        ))
      )}
      <span className="v2-audit-strip__summary">
        {spanCount > 0 && durationMs > 0 && (
          <>
            turn {formatMs(durationMs)} · {spanCount} span{spanCount !== 1 ? 's' : ''} · cost{' '}
            {formatUsd(costUsd)}{' '}
          </>
        )}
        {langfuseBaseUrl && correlationId && (
          <a
            href={`${langfuseBaseUrl.replace(/\/$/, '')}/trace/${encodeURIComponent(correlationId)}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: traceColor, textDecoration: 'none' }}
          >
            ⌥L Langfuse →
          </a>
        )}
      </span>
    </div>
  );
}
