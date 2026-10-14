/**
 * ClientTraceStripV3 — user-visible moments only (roadmap item #7).
 *
 * Replaces v2's raw TimelineV2 span firehose on the client surface. The
 * client doesn't need to see 'market_specialist.tool_call_start' or
 * 'compliance_specialist.completed' — those are Sarah/Marcus concerns.
 *
 * This strip shows only the handful of moments Eleanor WOULD see:
 *   • "You sent a message" (client typed)
 *   • "Liaison replied" (brief.completeTurn fired)
 *   • "MNPI screen cleared" (gate_event mnpi_filter passed)
 *   • "Audit entry written" (gate_event audit passed)
 *   • "Handed off to your advisor" (queue_update alerts or briefs entry)
 *
 * If a step fails, we render it red with a human-readable explanation
 * ("Audit delayed — your advisor has been notified").
 *
 * Data sources:
 *   - useTraversalStore: startedAt, turnId, nodes (for gate state)
 *   - useBriefStore: markdown, isStreaming, durationMs
 *   - useQueuesStore: last queue_update timestamp by queue
 *
 * The strip auto-collapses to 'You sent a message · waiting…' until the
 * first event fires, to avoid looking empty on load.
 */

import { useMemo } from 'react';
import { useTraversalStore } from '../../shared/store/traversal';
import { useBriefStore } from '../../shared/store/brief';
import { useQueuesStore } from '../../shared/store/queues';

type Status = 'pending' | 'active' | 'done' | 'error';

interface Step {
  id: string;
  label: string;
  subtext?: string;
  status: Status;
  timestamp?: number;
}

function formatElapsed(startMs: number, endMs: number): string {
  const delta = Math.max(0, endMs - startMs);
  if (delta < 1000) return `${delta}ms`;
  const s = (delta / 1000).toFixed(1);
  return `${s}s`;
}

export function ClientTraceStripV3() {
  const turnId = useTraversalStore((s) => s.turnId);
  const startedAt = useTraversalStore((s) => s.startedAt);
  const storeNodes = useTraversalStore((s) => s.nodes);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const briefTurnId = useBriefStore((s) => s.turnId);
  const durationMs = useBriefStore((s) => s.durationMs);
  const queueItems = useQueuesStore((s) => s.itemsByQueue);

  const steps = useMemo<Step[]>(() => {
    // Early-return "waiting for your message" when no turn has started.
    if (!turnId || !startedAt) {
      return [
        {
          id: 'client:sent',
          label: 'Waiting for your message',
          status: 'pending',
          subtext: 'Type below to begin',
        },
      ];
    }

    const mnpi = storeNodes['gate:mnpi_filter'];
    const audit = storeNodes['gate:audit'];
    const liaisonOrch = storeNodes['liaison_orchestrator'];

    // Any item landed in the advisor-facing queues (alerts/briefs/pending)
    // counts as a hand-off to the RM. The queues store keys items per-queue.
    const handoffCandidates = [
      ...(queueItems.alerts ?? []),
      ...(queueItems.briefs ?? []),
      ...(queueItems.pending ?? []),
    ];
    const handoffLatest = handoffCandidates.reduce<number>((acc, item) => {
      const ts = new Date(item.timestamp ?? 0).getTime();
      return Number.isFinite(ts) && ts > acc ? ts : acc;
    }, 0);

    const replied = !isStreaming && briefTurnId === turnId && durationMs > 0;

    const mnpiStatus: Status =
      mnpi?.state === 'solid'
        ? 'done'
        : mnpi?.state === 'error'
          ? 'error'
          : mnpi?.state === 'pulse'
            ? 'active'
            : 'pending';

    const auditStatus: Status =
      audit?.state === 'solid'
        ? 'done'
        : audit?.state === 'error'
          ? 'error'
          : audit?.state === 'pulse'
            ? 'active'
            : 'pending';

    const handoffStatus: Status = handoffLatest > 0 ? 'done' : 'pending';

    const now = Date.now();

    return [
      {
        id: 'client:sent',
        label: 'You sent a message',
        status: 'done',
        timestamp: startedAt,
      },
      {
        id: 'liaison:replied',
        label: replied ? 'Liaison replied' : 'Liaison is thinking…',
        subtext: replied
          ? `took ${formatElapsed(startedAt, startedAt + durationMs)}`
          : liaisonOrch?.state === 'pulse'
            ? 'your message is being analysed'
            : undefined,
        status: replied ? 'done' : liaisonOrch?.state === 'pulse' ? 'active' : 'pending',
        timestamp: replied ? startedAt + durationMs : undefined,
      },
      {
        id: 'mnpi:cleared',
        label: 'MNPI screen cleared',
        subtext:
          mnpiStatus === 'error'
            ? 'flagged for review'
            : mnpiStatus === 'pending'
              ? 'not reached yet'
              : undefined,
        status: mnpiStatus,
      },
      {
        id: 'audit:written',
        label: 'Audit entry written',
        subtext:
          auditStatus === 'error'
            ? 'audit delayed · advisor was notified'
            : auditStatus === 'pending'
              ? 'not reached yet'
              : undefined,
        status: auditStatus,
      },
      {
        id: 'rm:handoff',
        label: 'Handed off to your advisor',
        subtext:
          handoffStatus === 'done'
            ? `in advisor queue · ${formatElapsed(handoffLatest, now)} ago`
            : 'queue pending',
        status: handoffStatus,
        timestamp: handoffStatus === 'done' ? handoffLatest : undefined,
      },
    ];
  }, [turnId, startedAt, storeNodes, isStreaming, briefTurnId, durationMs, queueItems]);

  return (
    <div className="v3-client-trace" aria-label="What happened on this turn" data-testid="client-trace-strip">
      <div className="v3-client-trace__title">Behind this turn</div>
      <ol className="v3-client-trace__list">
        {steps.map((s) => (
          <li
            key={s.id}
            className="v3-client-trace__item"
            data-status={s.status}
          >
            <span className="v3-client-trace__bullet" aria-hidden="true" />
            <div className="v3-client-trace__content">
              <span className="v3-client-trace__label">{s.label}</span>
              {s.subtext && (
                <span className="v3-client-trace__subtext">{s.subtext}</span>
              )}
            </div>
            {s.timestamp && (
              <span className="v3-client-trace__time fsi-mono">
                {new Date(s.timestamp).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
