/**
 * Client Channel — WhatsApp-style web mockup. Channel-native, NOT a portal.
 * Permanent disclaimer. No positions, no numbers. CTA row above the composer.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatBubble } from './ChatBubble';
import { CtaButtons } from './CtaButtons';
import { ErrorBoundary } from '../../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../../shared/hooks/useStreamingTurn';
import { useBriefStore } from '../../../shared/store/brief';

interface Message {
  id: string;
  from: 'client' | 'agent';
  text: string;
  timestamp: string;
}

export interface ClientChannelProps {
  onAuthExpired?: () => void;
}

export function ClientChannel({ onAuthExpired }: ClientChannelProps) {
  const [composer, setComposer] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const threadRef = useRef<HTMLDivElement>(null);

  const appendAgentFromStore = useCallback(() => {
    const { markdown, isStreaming } = useBriefStore.getState();
    if (!markdown || isStreaming) return;
    setMessages((prev) => {
      const lastAgent = [...prev].reverse().find((m) => m.from === 'agent');
      if (lastAgent?.text === markdown) return prev;
      return [
        ...prev,
        {
          id: crypto.randomUUID(),
          from: 'agent',
          text: markdown,
          timestamp: new Date().toISOString(),
        },
      ];
    });
    useBriefStore.getState().reset();
  }, []);

  const handleMessage = useStreamingTurn({
    onError: () => undefined,
  });

  useEffect(() => {
    const t = setInterval(appendAgentFromStore, 600);
    return () => clearInterval(t);
  }, [appendAgentFromStore]);

  const { send } = useAgentSocket({ onMessage: handleMessage, onAuthExpired });

  const emitClientTurn = useCallback(
    (text: string) => {
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), from: 'client', text, timestamp: new Date().toISOString() },
      ]);
      send({ type: 'turn', turn_id: crypto.randomUUID(), text });
      useBriefStore.getState().reset();
    },
    [send],
  );

  const submit = useCallback(() => {
    if (!composer.trim()) return;
    emitClientTurn(composer.trim());
    setComposer('');
  }, [composer, emitClientTurn]);

  const askRm = useCallback(() => {
    emitClientTurn('Please connect me with my RM.');
  }, [emitClientTurn]);

  const scheduleCall = useCallback(() => {
    emitClientTurn('Please schedule a call with my RM.');
  }, [emitClientTurn]);

  useEffect(() => {
    const el = threadRef.current;
    if (el && typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  return (
    <ErrorBoundary>
      <div className="client-root" role="application" aria-label="Client channel">
        <div className="client-header">
          <div className="client-header__avatar" aria-hidden="true">
            WA
          </div>
          <div>
            <div className="client-header__name">Your Wealth Team</div>
            <div style={{ fontSize: '0.75rem', opacity: 0.85 }}>online</div>
          </div>
        </div>
        <div
          className="client-thread"
          ref={threadRef}
          role="log"
          aria-live="polite"
          aria-atomic="false"
        >
          {messages.length === 0 && (
            <ChatBubble
              from="agent"
              text="Hi — I can help with general questions. For recommendations, I'll loop in your RM."
              timestamp={new Date().toISOString()}
            />
          )}
          {messages.map((m) => (
            <ChatBubble key={m.id} from={m.from} text={m.text} timestamp={m.timestamp} />
          ))}
        </div>
        <div className="client-disclaimer" role="note">
          For informational purposes. Your RM makes recommendations.
        </div>
        <CtaButtons onScheduleCall={scheduleCall} onAskRm={askRm} />
        <form
          className="client-composer"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <input
            type="text"
            aria-label="Message"
            placeholder="Type a message"
            value={composer}
            onChange={(e) => setComposer(e.target.value)}
          />
          <button type="submit" aria-label="Send">
            ➤
          </button>
        </form>
      </div>
    </ErrorBoundary>
  );
}
