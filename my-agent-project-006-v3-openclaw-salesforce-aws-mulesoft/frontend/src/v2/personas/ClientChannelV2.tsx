/**
 * Client Channel v2 — Eleanor Vance's WhatsApp surface inside a phone bezel.
 *
 * 3-column layout: left caption ("Client surface: channel-native") · phone
 * mockup with live chat · right caption with embedded trust-spine reveal
 * (compact map + timeline). The right-side reveal is the "one spine, three
 * surfaces" payoff.
 *
 * Real wiring:
 *   - WebSocket: useAgentSocket (existing)
 *   - Turn streaming: useStreamingTurn → brief store
 *   - Messages: prepend client turns + append agent response when brief completes
 *   - Traversal map + timeline: same stores as Sarah's and Marcus's screens,
 *     proving the spine is shared
 *
 * MNPI redaction is server-side (never in the UI) — this panel never renders
 * positions, numbers, or restricted content. CTA handlers emit canonical turn
 * text: "Please connect me with my RM" etc.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { PersonaHeaderV2 } from '../atoms/PersonaHeaderV2';
import { TraversalMapV2 } from '../atoms/TraversalMapV2';
import { TimelineV2 } from '../atoms/TimelineV2';
import { AuditStripV2 } from '../atoms/AuditStripV2';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useBriefStore } from '../../shared/store/brief';
import { useSessionStore } from '../../shared/store/session';

interface Message {
  id: string;
  from: 'client' | 'agent' | 'rm';
  name?: string;
  text: string;
  timestamp: string;
  /** When set, render a "rich" inline card with a title + body inside the bubble. */
  rich?: { title: string; body: string };
}

function shortTime(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

function PhoneBezel({
  messages,
  disclaimer,
  onComposerSubmit,
  onSchedule,
  onAskRm,
  connectionStatus,
}: {
  messages: Message[];
  disclaimer: string;
  onComposerSubmit: (text: string) => void;
  onSchedule: () => void;
  onAskRm: () => void;
  connectionStatus: string;
}) {
  const [composer, setComposer] = useState('');
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = threadRef.current;
    if (el && typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!composer.trim()) return;
    onComposerSubmit(composer.trim());
    setComposer('');
  };

  return (
    <div className="v2-phone" role="img" aria-label="Client channel phone mockup">
      <div className="v2-phone__notch" />
      <div className="v2-phone__screen">
        <div className="v2-phone__statusbar">
          <span className="w360-mono">9:41</span>
          <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            <span className="w360-mono" style={{ fontSize: 10 }}>● 5G</span>
            <span className="w360-mono" style={{ fontSize: 10 }}>96%</span>
          </span>
        </div>
        <div className="v2-client-header">
          <span className="v2-client-header__back">‹</span>
          <div className="v2-client-header__avatar">W360</div>
          <div>
            <div className="v2-client-header__name">Your Wealth Team</div>
            <div className="v2-client-header__status">
              {connectionStatus === 'open' ? 'online' : connectionStatus}
            </div>
          </div>
          <div className="v2-client-header__icons">
            <span aria-hidden="true">📞</span>
            <span aria-hidden="true">⋮</span>
          </div>
        </div>
        <div className="v2-client-thread" ref={threadRef} role="log" aria-live="polite">
          <div className="v2-client-day">TODAY</div>
          {messages.length === 0 && (
            <div
              className="v2-bubble v2-bubble--in"
              style={{ alignSelf: 'flex-start' }}
            >
              Good morning. I can help with general questions. For positions or changes, I'll loop
              in your RM.
              <span className="v2-bubble__time">{shortTime(new Date().toISOString())}</span>
            </div>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={
                m.from === 'client'
                  ? 'v2-bubble v2-bubble--out'
                  : 'v2-bubble v2-bubble--in'
              }
            >
              {m.name && <div className="v2-bubble__name">{m.name}</div>}
              {m.text}
              {m.rich && (
                <div className="v2-bubble__rich">
                  <div className="v2-bubble__rich-title">{m.rich.title}</div>
                  {m.rich.body}
                </div>
              )}
              <span className="v2-bubble__time">{shortTime(m.timestamp)}</span>
            </div>
          ))}
        </div>
        <div className="v2-client-disclaimer">
          <span aria-hidden="true">ⓘ</span> {disclaimer}
        </div>
        <div className="v2-client-ctas">
          <button type="button" data-variant="primary" onClick={onSchedule}>
            📅 Schedule call
          </button>
          <button type="button" data-variant="secondary" onClick={onAskRm}>
            👤 Ask my RM
          </button>
        </div>
        <form className="v2-client-composer" onSubmit={submit}>
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
    </div>
  );
}

export interface ClientChannelV2Props {
  onAuthExpired?: () => void;
}

export function ClientChannelV2({ onAuthExpired }: ClientChannelV2Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;

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
  const connectionStatus = useSessionStore((s) => s.connectionStatus);

  const emitClientTurn = useCallback(
    (text: string) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          from: 'client',
          text,
          timestamp: new Date().toISOString(),
        },
      ]);
      send({ type: 'turn', turn_id: crypto.randomUUID(), text });
      useBriefStore.getState().reset();
    },
    [send],
  );

  const askRm = useCallback(() => emitClientTurn('Please connect me with my RM.'), [emitClientTurn]);
  const scheduleCall = useCallback(
    () => emitClientTurn('Please schedule a call with my RM.'),
    [emitClientTurn],
  );

  return (
    <ErrorBoundary>
      <div className="v2-client-stage" data-screen-label="03 Client Liaison Channel">
        <div style={{ overflowY: 'auto' }}>
          <PersonaHeaderV2 persona="fsi_client_liaison" surface="channel" />
          <div className="v2-client-grid">
            <div className="v2-client-caption">
              <div className="v2-client-caption__eyebrow">Client surface</div>
              <h1 className="v2-client-caption__title">Channel-native, not a portal.</h1>
              <p className="v2-client-caption__body">
                Eleanor opens WhatsApp like any morning. The Liaison agent answers FAQs, recognises
                intent shifts that require a human, and queues a hand-off to her RM. It never quotes
                positions or numbers.
              </p>
              <ul className="v2-client-caption__list">
                <li><strong>FAQ tier</strong> — Haiku-class. No vendor calls, read-only.</li>
                <li><strong>Hand-off tier</strong> — queues an Insight in Marcus's workbench.</li>
                <li><strong>Disclaimer is permanent</strong> — informational only.</li>
                <li><strong>MNPI safe</strong> — redactions applied server-side.</li>
              </ul>
            </div>

            <PhoneBezel
              messages={messages}
              disclaimer="For informational purposes. Your RM makes recommendations."
              onComposerSubmit={emitClientTurn}
              onSchedule={scheduleCall}
              onAskRm={askRm}
              connectionStatus={connectionStatus}
            />

            <div className="v2-client-caption">
              <div className="v2-client-caption__eyebrow">Behind the scenes</div>
              <h1 className="v2-client-caption__title">One trust spine. Three surfaces.</h1>
              <p className="v2-client-caption__body">
                Eleanor sees a chat. But every turn flows through the same orchestrator, MNPI
                filter, and audit gate that powers Sarah's research brief and Marcus's order plan.
              </p>
              <div className="v2-client-tracestack">
                <TraversalMapV2
                  fallbackPersona="fsi_client_liaison"
                  langfuseBaseUrl={langfuseBaseUrl}
                />
                <TimelineV2 persona="fsi_client_liaison" langfuseBaseUrl={langfuseBaseUrl} />
              </div>
            </div>
          </div>
        </div>
        <AuditStripV2 langfuseBaseUrl={langfuseBaseUrl} />
      </div>
    </ErrorBoundary>
  );
}
