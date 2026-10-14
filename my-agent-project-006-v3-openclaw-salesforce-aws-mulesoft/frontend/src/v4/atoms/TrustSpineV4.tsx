/**
 * V4 Trust Spine — V2-shape: one collapsible panel holding the
 * Architecture Map stacked OVER the End-to-End Timeline.
 *
 * Earlier V4 put map + timeline side-by-side. That cramped both in
 * ~600px halves at real viewport widths — the layout you correctly
 * called "hotchpotch" in the screenshot review. V2's approach wins:
 * each section gets full width and enough vertical space.
 *
 * Grammar:
 *   <details className="v4-map-panel" open>
 *     <summary>Trust spine — live</summary>
 *     <TraversalMapV4 />
 *     <TimelineV4 />
 *   </details>
 *
 * Closed by default? No — open by default to match V2's demo cadence.
 * Each section stays scroll-reachable but the chrome is quieter than
 * rendering them both in the main flow.
 */

import { useState, type ReactNode } from 'react';
import type { GateState } from '../../shared/types/api';
import type { Persona } from '../../shared/types/persona';
import { TraversalMapV4 } from './TraversalMapV4';
import { TimelineV4 } from './TimelineV4';

export interface TrustSpineV4Props {
  persona: Persona;
  eyebrowLeft?: ReactNode;
  eyebrowRight?: ReactNode;
  gates?: GateState[];
  langfuseBaseUrl?: string;
  /** When false, the panel starts collapsed. Defaults to true — the demo
   * opens with the trust spine visible so the architecture reads. */
  defaultOpen?: boolean;
}

export function TrustSpineV4({
  persona,
  eyebrowLeft,
  eyebrowRight,
  gates,
  langfuseBaseUrl,
  defaultOpen = true,
}: TrustSpineV4Props) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <details
      className="v4-map-panel"
      open={isOpen || undefined}
      data-testid="trust-spine-v4"
      onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary>
        <span>
          {eyebrowLeft ?? (
            <>
              Trust spine — <strong>live</strong>
            </>
          )}
        </span>
        {eyebrowRight && <span className="v4-map-panel__meta">{eyebrowRight}</span>}
      </summary>
      <div className="v4-map-panel__stack">
        <TraversalMapV4 persona={persona} langfuseBaseUrl={langfuseBaseUrl} />
        <TimelineV4 persona={persona} gates={gates} langfuseBaseUrl={langfuseBaseUrl} />
      </div>
    </details>
  );
}
