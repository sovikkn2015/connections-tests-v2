/**
 * Pipeline Tracker — shows AutoResearchClaw pipeline progress.
 * 23 stages grouped by phase (A-H). Current stage highlighted. HITL gates marked.
 */

import { useMemo } from 'react';
import { useAgentStore } from '../store/agentStore';

const PHASE_COLORS: Record<string, string> = {
  'A: Intake': '#1589ee',
  'B: Data Collection': '#0070d2',
  'C: Validation': '#ff9e2c',
  'D: Analysis': '#9050e9',
  'E: Review': '#ff9e2c',
  'F: Synthesis': '#04844b',
  'G: Output': '#e87400',
  'H: Delivery': '#c23934',
};

export default function PipelineTracker() {
  const { pipelineStages, currentStageId } = useAgentStore();

  const completedCount = pipelineStages.filter((s) => s.status === 'completed').length;
  const totalCount = pipelineStages.length;
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  const phases = useMemo(
    () => Array.from(new Set(pipelineStages.map((s) => s.phase))),
    [pipelineStages],
  );

  const stagesByPhase = useMemo(
    () => {
      const map = new Map<string, typeof pipelineStages>();
      for (const stage of pipelineStages) {
        const list = map.get(stage.phase) || [];
        list.push(stage);
        map.set(stage.phase, list);
      }
      return map;
    },
    [pipelineStages],
  );

  return (
    <div className="ir-pipeline-tracker" aria-label="Pipeline progress tracker">
      <div className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-m-bottom_xx-small">
        <span className="slds-text-body_small" style={{ fontWeight: 600 }}>
          AutoResearchClaw Pipeline
        </span>
        <span className="slds-text-body_small slds-text-color_weak">
          {completedCount}/{totalCount} stages ({progressPct}%)
        </span>
      </div>

      <div
        style={{ height: 4, background: '#e5e5e5', borderRadius: 2, marginBottom: 8 }}
        role="progressbar"
        aria-valuenow={progressPct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Pipeline ${progressPct}% complete`}
      >
        <div style={{ height: '100%', width: `${progressPct}%`, background: '#04844b', borderRadius: 2, transition: 'width 0.3s' }} />
      </div>

      <div className="slds-grid slds-wrap" style={{ gap: '4px 12px' }}>
        {phases.map((phase) => (
          <div key={phase} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <span className="slds-text-body_small" style={{ fontSize: '0.5625rem', color: PHASE_COLORS[phase] || '#706e6b', fontWeight: 600, marginRight: 2, whiteSpace: 'nowrap' }}>
              {phase.split(':')[0]}
            </span>
            {(stagesByPhase.get(phase) || []).map((stage) => {
                const isCurrent = stage.id === currentStageId;
                const statusClass = stage.status === 'gate' ? 'gate' : stage.status;
                return (
                  <div
                    key={stage.id}
                    className={`ir-pipeline-stage ir-pipeline-stage--${statusClass}`}
                    style={isCurrent ? { outline: '2px solid #0070d2', outlineOffset: 1 } : undefined}
                    title={`${stage.id}. ${stage.name} (${stage.status})${stage.isHitlGate ? ' — HITL Gate' : ''}`}
                    aria-label={`Stage ${stage.id}: ${stage.name}, status: ${stage.status}`}
                    tabIndex={0}
                    role="button"
                  >
                    {stage.isHitlGate ? '\u2298' : stage.id}
                  </div>
                );
              })}
          </div>
        ))}
      </div>
    </div>
  );
}
