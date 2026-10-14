/**
 * Center column — RM's conversation with the agent. Query input at the
 * bottom, response stream above. Hosts the inline HITL approval when an
 * ActionPlan is in flight.
 */

import { useCallback, useState } from 'react';
import { StreamingText } from '../../../shared/components/StreamingText';
import { HitlApprovalDialog } from './HitlApprovalDialog';
import { useBriefStore } from '../../../shared/store/brief';
import { useOptimisticApproval } from '../../../shared/hooks/useOptimisticApproval';
import type { OutboundMessage } from '../../../shared/types/agent';
import type { ActionPlan } from '../../../shared/types/api';

type OptimisticApproval = ReturnType<typeof useOptimisticApproval>;

export interface ConversationPanelProps {
  send: (m: OutboundMessage) => void;
  principalId: string;
  pendingPlan: ActionPlan | null;
  /** Optional approval instance lifted to AdvisorScreen (P1.6). If omitted
   * the panel falls back to an owned instance so the component stays
   * self-sufficient for isolated tests. */
  approval?: OptimisticApproval;
  onOpenCitation?: (sourceId: string) => void;
}

export function ConversationPanel({
  send,
  principalId,
  pendingPlan,
  approval,
  onOpenCitation,
}: ConversationPanelProps) {
  const [query, setQuery] = useState('');
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const reset = useBriefStore((s) => s.reset);

  const ownApproval = useOptimisticApproval({ send, principalId });
  const effectiveApproval = approval ?? ownApproval;

  const submit = useCallback(() => {
    if (!query.trim()) return;
    reset();
    send({ type: 'turn', turn_id: crypto.randomUUID(), text: query });
  }, [query, reset, send]);

  return (
    <div className="advisor-column">
      <div className="advisor-column__header">Conversation</div>
      <div className="advisor-conversation">
        {pendingPlan && (
          <HitlApprovalDialog
            plan={pendingPlan}
            state={effectiveApproval.state}
            onApprove={effectiveApproval.approve}
            onReject={effectiveApproval.reject}
          />
        )}
        <div
          style={{
            background: '#FFFFFF',
            padding: '0.5rem 0.75rem',
            borderRadius: '0.25rem',
            border: '1px solid var(--v3-border)',
            minHeight: '4rem',
          }}
        >
          {markdown ? (
            <StreamingText
              markdown={markdown}
              citations={citations}
              isStreaming={isStreaming}
              onOpenCitation={onOpenCitation}
            />
          ) : (
            <span style={{ color: '#706E6B', fontSize: '0.875rem' }}>
              Ask a question about your book. Example: "Which of my clients have NVDA exposure
              above 5%?"
            </span>
          )}
        </div>
      </div>
      <div
        style={{
          padding: '0.5rem',
          borderTop: '1px solid var(--v3-border)',
          display: 'flex',
          gap: '0.5rem',
        }}
      >
        <input
          type="text"
          aria-label="Advisor query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask the platform…"
          style={{
            flex: 1,
            padding: '0.375rem 0.5rem',
            border: '1px solid var(--v3-border)',
            borderRadius: '0.25rem',
            fontFamily: 'inherit',
          }}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit();
          }}
        />
        <button type="button" className="slds-button slds-button_brand" onClick={submit}>
          Submit
        </button>
      </div>
    </div>
  );
}
