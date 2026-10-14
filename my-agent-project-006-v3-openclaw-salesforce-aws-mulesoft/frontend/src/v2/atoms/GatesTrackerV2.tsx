/**
 * v2 Seven-gate tracker — always visible, always shows all 7 gates.
 *
 * Gates fire in canonical order (guardrails → mnpi_filter → compliance →
 * hitl → dual_auth → mulesoft → audit). Each cell shows number + name +
 * detail + latency. Driven from useGateTracker's GateState[] which is
 * already fed by gate_passed/gate_started/gate_failed events from the
 * WebSocket.
 *
 * Unlike v1's SevenGateTracker (which is only mounted when a plan is in
 * flight), this one renders ALL seven even when idle so the RM sees the
 * full path and can see where we are in it.
 */

import type { GateState } from '../../shared/types/api';

const LABELS: Record<
  GateState['name'],
  { num: string; name: string; defaultDetail: string }
> = {
  guardrails: { num: '①', name: 'Guardrails', defaultDetail: 'input shape · roles · scope' },
  mnpi_filter: { num: '②', name: 'MNPI Filter', defaultDetail: 'server-side redactions' },
  compliance: { num: '③', name: 'Compliance', defaultDetail: 'screen · suitability' },
  hitl: { num: '④', name: 'HITL', defaultDetail: 'RM approval' },
  dual_auth: { num: '⑤', name: 'Dual-Auth', defaultDetail: 'second approver' },
  mulesoft: { num: '⑥', name: 'MuleSoft', defaultDetail: 'broker / OMS submit' },
  audit: { num: '⑦', name: 'Audit', defaultDetail: 'Langfuse · S3 · CRM' },
};

function latency(g: GateState): string {
  if (g.status === 'pending' || g.status === 'skipped') return '—';
  if (g.status === 'in_progress') return '…';
  if (!g.started_at || !g.completed_at) return '—';
  const ms = Math.max(0, Date.parse(g.completed_at) - Date.parse(g.started_at));
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export interface GatesTrackerV2Props {
  gates: GateState[];
}

export function GatesTrackerV2({ gates }: GatesTrackerV2Props) {
  return (
    <div className="v2-gates" role="progressbar" aria-label="Seven-gate write path">
      {gates.map((g, i) => {
        const meta = LABELS[g.name];
        const detail = g.detail ?? meta.defaultDetail;
        return (
          <div
            key={g.name}
            className="v2-gate"
            data-status={g.status}
            data-testid={`v2-gate-${g.name}`}
            aria-label={`${meta.num} ${meta.name} — ${g.status}`}
          >
            <span className="v2-gate__num">
              {meta.num} gate {i + 1} / 7
            </span>
            <span className="v2-gate__name">{meta.name}</span>
            <span className="v2-gate__detail">
              {detail} · {latency(g)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
