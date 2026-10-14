/**
 * TrustSpineStrip — map + timeline side-by-side or stacked.
 *
 * The eyebrow row explicitly calls out "same orchestrator graph as <sibling>
 * persona" — this is the payoff line for the three-surfaces-one-spine story.
 */

import { TraversalMapV2 } from './TraversalMapV2';
import { TimelineV2 } from './TimelineV2';
import type { GateState } from '../../shared/types/api';
import type { Persona } from '../../shared/types/persona';
import { useBriefStore } from '../../shared/store/brief';
import { useTraversalStore } from '../../shared/store/traversal';

export interface TrustSpineStripProps {
  persona: Persona;
  gates?: GateState[];
  stacked?: boolean;
  langfuseBaseUrl?: string;
  eyebrowText?: string;
}

const SIBLING_HINT: Record<Persona, string> = {
  fsi_research: 'same orchestrator graph that powers Marcus\'s plan and Eleanor\'s channel',
  fsi_advisor: 'same orchestrator graph as Sarah\'s research — now lit through advisor_orch',
  fsi_client_liaison: 'same trust spine — now lit through liaison_orch',
};

export function TrustSpineStrip({
  persona,
  gates,
  stacked = false,
  langfuseBaseUrl,
  eyebrowText,
}: TrustSpineStripProps) {
  const turnId = useBriefStore((s) => s.turnId);
  const activePersona = useTraversalStore((s) => s.activePersona);

  const turnRef = turnId ? `turn ${turnId.slice(0, 8)}` : '—';
  const personaLabel = activePersona === persona || activePersona === null
    ? persona.replace(/^fsi_/, '')
    : `${activePersona.replace(/^fsi_/, '')} → ${persona.replace(/^fsi_/, '')}`;

  return (
    <div className={`v2-trust-spine${stacked ? ' v2-trust-spine--stacked' : ''}`}>
      <div className="v2-trust-spine__eyebrow">
        <span>
          <strong>Trust spine</strong> · {eyebrowText ?? SIBLING_HINT[persona]}
        </span>
        <span className="w360-mono">
          {personaLabel} · {turnRef}
        </span>
      </div>
      <TraversalMapV2
        fallbackPersona={persona}
        showGates={persona === 'fsi_advisor'}
        langfuseBaseUrl={langfuseBaseUrl}
      />
      <TimelineV2 persona={persona} gates={gates} langfuseBaseUrl={langfuseBaseUrl} />
    </div>
  );
}
