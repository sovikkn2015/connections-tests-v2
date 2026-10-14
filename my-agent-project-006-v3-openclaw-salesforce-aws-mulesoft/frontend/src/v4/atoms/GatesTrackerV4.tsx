/**
 * V4 Seven-Gate Tracker — ported from the uploaded design's GatesTracker.
 *
 * Reads live gate state from the useGateTracker hook (v2 atom uses the
 * same hook). Each gate goes passed → active → pending visually by the
 * border-top stripe; active gate gets the animated scan line.
 */

import type { GateState, GateName } from '../../shared/types/api';

interface GateDef {
  num: string;
  name: GateName;
  label: string;
  detail: string;
}

const GATE_DEFS: GateDef[] = [
  { num: '①', name: 'guardrails', label: 'Guardrails', detail: 'input · roles · scope' },
  { num: '②', name: 'mnpi_filter', label: 'MNPI Filter', detail: 'redactions · ok' },
  { num: '③', name: 'compliance', label: 'Compliance', detail: 'screen · suitability' },
  { num: '④', name: 'hitl', label: 'HITL', detail: 'RM approval · pending' },
  { num: '⑤', name: 'dual_auth', label: 'Dual-Auth', detail: 'second approver' },
  { num: '⑥', name: 'mulesoft', label: 'MuleSoft', detail: 'broker / OMS submit' },
  { num: '⑦', name: 'audit', label: 'Audit', detail: 'Langfuse · S3 · CRM' },
];

function formatLat(g: GateState): string {
  if (g.started_at && g.completed_at) {
    const ms = Date.parse(g.completed_at) - Date.parse(g.started_at);
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
  if (g.status === 'in_progress') return '…';
  return '—';
}

function statusFor(g: GateState | undefined): 'pending' | 'active' | 'passed' | 'failed' {
  if (!g) return 'pending';
  if (g.status === 'passed' || g.status === 'skipped') return 'passed';
  if (g.status === 'failed') return 'failed';
  if (g.status === 'in_progress') return 'active';
  return 'pending';
}

export interface GatesTrackerV4Props {
  gates: GateState[];
}

export function GatesTrackerV4({ gates }: GatesTrackerV4Props) {
  const byName = new Map(gates.map((g) => [g.name, g]));

  return (
    <div className="gates" role="progressbar" aria-label="Seven-gate write path" aria-valuenow={gates.filter((g) => g.status === 'passed').length} aria-valuemin={0} aria-valuemax={7}>
      {GATE_DEFS.map((def, i) => {
        const g = byName.get(def.name);
        const status = statusFor(g);
        const detail = g?.detail ?? def.detail;
        return (
          <div key={def.name} className="gate" data-status={status} data-testid={`gate-v4-${def.name}`}>
            <span className="gate__num">
              {def.num} gate {i + 1} / 7
            </span>
            <span className="gate__name">{def.label}</span>
            <span className="gate__detail">
              {detail} · {g ? formatLat(g) : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}
