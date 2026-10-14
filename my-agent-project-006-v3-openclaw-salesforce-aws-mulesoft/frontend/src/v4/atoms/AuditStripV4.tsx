/**
 * V4 Audit Strip — 28px bar pinned to bottom. Real trace id +
 * connection status + running-span pills + Langfuse hotkey hint.
 *
 * Ported verbatim from the uploaded design. Wired to live session +
 * brief stores instead of the designer's mock pill array.
 */

import { useBriefStore } from '../../shared/store/brief';
import { useSessionStore } from '../../shared/store/session';
import type { ToolCall } from '../../shared/types/api';

function formatMs(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function pillColor(status: ToolCall['status']): string {
  if (status === 'ok') return 'var(--v4-success-300)';
  if (status === 'error') return 'var(--v4-error-300)';
  return 'var(--v4-warning-300)';
}

export interface AuditStripV4Props {
  className?: string;
}

export function AuditStripV4({ className }: AuditStripV4Props) {
  const correlationId = useSessionStore((s) => s.correlationId);
  const connectionStatus = useSessionStore((s) => s.connectionStatus);
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const durationMs = useBriefStore((s) => s.durationMs);
  const costUsd = useBriefStore((s) => s.costUsd);

  // Collapse per-agent: show one pill per agent_id with its best-known status.
  const byAgent = new Map<string, ToolCall['status']>();
  for (const tc of toolCalls) {
    const existing = byAgent.get(tc.agent_id);
    if (existing === 'error') continue;
    if (tc.status === 'error') {
      byAgent.set(tc.agent_id, 'error');
    } else if (existing === undefined || existing !== tc.status) {
      byAgent.set(tc.agent_id, tc.status);
    }
  }
  const pills = Array.from(byAgent.entries());

  return (
    <div className={`audit-strip${className ? ' ' + className : ''}`} role="status" data-testid="audit-strip-v4">
      <span style={{ color: 'var(--v4-forensic-text-4)' }}>trace</span>
      <span style={{ color: 'var(--v4-brand-500)' }}>
        {correlationId ? correlationId.slice(0, 16) : '—'}
      </span>
      <span style={{ color: 'var(--v4-forensic-text-4)' }}>·</span>
      <span
        style={{
          color:
            connectionStatus === 'open'
              ? 'var(--v4-success-300)'
              : connectionStatus === 'closed' || connectionStatus === 'error'
                ? 'var(--v4-error-300)'
                : 'var(--v4-warning-300)',
        }}
      >
        ● ws: {connectionStatus}
      </span>
      <span style={{ color: 'var(--v4-forensic-text-4)' }}>·</span>
      {pills.map(([agent, status]) => {
        const c = pillColor(status);
        return (
          <span key={agent} className="audit-pill" style={{ borderColor: `${c}66`, color: c }}>
            {agent.replace(/_specialist$/, '-spec').replace(/_orchestrator$/, '-orch')}{' '}
            <span className="audit-pill__status">{status}</span>
          </span>
        );
      })}
      <span style={{ marginLeft: 'auto', color: 'var(--v4-forensic-text-4)' }}>
        {durationMs > 0 ? `turn ${formatMs(durationMs)}` : 'idle'}
        {' · '}
        {toolCalls.length} span{toolCalls.length === 1 ? '' : 's'}
        {costUsd > 0 ? ` · $${costUsd.toFixed(3)}` : ''}
        {' · ⌥L Langfuse'}
      </span>
    </div>
  );
}
