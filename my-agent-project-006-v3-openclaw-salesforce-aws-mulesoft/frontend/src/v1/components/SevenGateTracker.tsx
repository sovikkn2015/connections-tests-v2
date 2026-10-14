/**
 * Seven-gate visual — full path always visible. Each cell lights up as gate
 * events arrive. Sits at the top of the advisor screen when an ActionPlan is
 * in flight.
 */

import type { GateState } from '../../shared/types/api';

const LABEL: Record<GateState['name'], string> = {
  guardrails: '① Guardrails',
  mnpi_filter: '② MNPI',
  compliance: '③ Compliance',
  hitl: '④ HITL',
  dual_auth: '⑤ Dual-Auth',
  mulesoft: '⑥ MuleSoft',
  audit: '⑦ Audit',
};

export function SevenGateTracker({ gates }: { gates: GateState[] }) {
  return (
    <div className="v3-gates" role="progressbar" aria-label="Seven-gate write path progress">
      {gates.map((gate) => (
        <div
          key={gate.name}
          className="v3-gate"
          data-status={gate.status}
          data-testid={`gate-${gate.name}`}
          title={gate.detail ?? gate.name}
          aria-label={`${LABEL[gate.name]} — ${gate.status}`}
        >
          {LABEL[gate.name]}
        </div>
      ))}
    </div>
  );
}
