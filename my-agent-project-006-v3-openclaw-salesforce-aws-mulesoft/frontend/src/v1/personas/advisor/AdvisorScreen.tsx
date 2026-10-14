/**
 * RM full-screen advisor workbench.
 *
 * Top: persona header + seven-gate tracker (visible whenever an ActionPlan is
 *      in flight).
 * Body: queues (left), conversation (center), client context (right).
 * Bottom: audit strip.
 */

import { useRef, useState } from 'react';
import { PersonaHeader } from '../../components/PersonaHeader';
import { AuditStrip } from '../../components/AuditStrip';
import { EndToEndTrace } from '../../../shared/components/EndToEndTrace';
import { SevenGateTracker } from '../../components/SevenGateTracker';
import { ErrorBoundary } from '../../../shared/components/ErrorBoundary';
import { TraversalMapPanel } from '../../components/TraversalMapPanel';
import { QueuesPanel } from './QueuesPanel';
import { ConversationPanel } from './ConversationPanel';
import { ClientContextPanel } from './ClientContextPanel';
import { useAgentSocket } from '../../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../../shared/hooks/useStreamingTurn';
import { useGateTracker } from '../../../shared/hooks/useGateTracker';
import { useOptimisticApproval } from '../../../shared/hooks/useOptimisticApproval';
import { useQueuesStore } from '../../../shared/store/queues';
import { useSessionStore } from '../../../shared/store/session';
import type { ActionPlan } from '../../../shared/types/api';
import type { OutboundMessage } from '../../../shared/types/agent';

export interface AdvisorScreenProps {
  onAuthExpired?: () => void;
  onOpenCitation?: (sourceId: string) => void;
}

export function AdvisorScreen({ onAuthExpired, onOpenCitation }: AdvisorScreenProps) {
  const [pendingPlan, setPendingPlan] = useState<ActionPlan | null>(null);
  const principalId = useSessionStore((s) => s.principalId) ?? 'anonymous';
  const gateTracker = useGateTracker();
  const removeQueueItem = useQueuesStore((s) => s.removeItem);

  // P1.6: lift useOptimisticApproval so its confirm/rollback can be driven
  // by the streaming-turn reconciler. Send is a forwarder ref so the
  // approval hook can be instantiated before useAgentSocket resolves.
  const sendRef = useRef<(m: OutboundMessage) => void>(() => {
    /* pre-socket no-op */
  });
  const optimistic = useOptimisticApproval({
    send: (m) => sendRef.current(m),
    principalId,
  });

  const handleMessage = useStreamingTurn({
    onHitlPrompt: (ev) => {
      setPendingPlan(ev.plan);
      gateTracker.reset(ev.plan.plan_id);
    },
    onGate: gateTracker.handleGateEvent,
    onOptimisticConfirm: optimistic.confirm,
    onOptimisticRollback: optimistic.rollback,
    onQueueUpdate: (ev) => {
      if (ev.op === 'remove') {
        removeQueueItem(ev.queue, ev.item_id);
      }
    },
    onError: (ev) => {
      if (ev.tier === 'fatal') throw new Error(ev.error.message);
    },
  });

  const { send } = useAgentSocket({
    onMessage: handleMessage,
    onAuthExpired,
  });
  sendRef.current = send;

  const planInFlight = pendingPlan !== null || gateTracker.activePlanId !== null;

  return (
    <ErrorBoundary>
      <div className="advisor-root">
        <PersonaHeader persona="fsi_advisor" />
        {planInFlight && <SevenGateTracker gates={gateTracker.gates} />}
        <div className="advisor-body">
          <QueuesPanel />
          <ConversationPanel
            send={send}
            principalId={principalId}
            pendingPlan={pendingPlan}
            approval={optimistic}
            onOpenCitation={onOpenCitation}
          />
          <ClientContextPanel />
        </div>
        <TraversalMapPanel
        fallbackPersona="fsi_advisor"
        langfuseBaseUrl={import.meta.env.VITE_LANGFUSE_BASE_URL as string | undefined}
      />
        <EndToEndTrace />
        <AuditStrip />
      </div>
    </ErrorBoundary>
  );
}
