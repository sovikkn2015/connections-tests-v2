/**
 * Langfuse-trace-visible audit strip. One line, always on, at the bottom of
 * Sarah's and the RM's screens. Shows correlation id + active / completed
 * tool-call spans with real timings — not a summary (demo depth cue §1).
 */

import { useBriefStore } from '../../shared/store/brief';
import { useSessionStore } from '../../shared/store/session';

export function AuditStrip() {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const correlationId = useSessionStore((s) => s.correlationId);
  const connectionStatus = useSessionStore((s) => s.connectionStatus);

  return (
    <div className="v3-audit-strip" role="status" aria-label="Audit trace">
      <span className="v3-audit-strip__trace-id" title="Langfuse trace id">
        trace: {correlationId?.slice(0, 8) ?? '—'}
      </span>
      <span className="v3-audit-strip__trace-id">ws: {connectionStatus}</span>
      {toolCalls.length === 0 ? (
        <span className="v3-audit-strip__trace-id">no active spans</span>
      ) : (
        toolCalls.map((tc) => (
          <span
            key={tc.span_id}
            className="v3-audit-strip__span"
            data-status={tc.status}
            title={`${tc.agent_id} → ${tc.tool_name}`}
          >
            {tc.tool_name}
            {tc.latency_ms !== undefined && <span> · {tc.latency_ms}ms</span>}
          </span>
        ))
      )}
    </div>
  );
}
