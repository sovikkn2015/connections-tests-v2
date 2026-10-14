/**
 * Client Channel v3 — Eleanor Vance's WhatsApp surface.
 *
 * v3 over v2:
 *   - FSI Workforce 360 branding
 *   - TraversalMapV3 in `variant="client-simple"` (roadmap item #7) —
 *     a 5-node horizontal spine hiding specialist churn the client
 *     doesn't need to see.
 *   - ClientTraceStripV3 replaces TimelineV2 firehose with
 *     user-visible moments only (sent · liaison replied · MNPI cleared ·
 *     audit written · handed off).
 *   - No theme toggle on the green WhatsApp header (brand-locked).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { PersonaHeaderV3 } from '../atoms/PersonaHeaderV3';
import { TraversalMapV3 } from '../atoms/TraversalMapV3';
import { ClientTraceStripV3 } from '../atoms/ClientTraceStripV3';
import { AuditStripV2 } from '../../v2/atoms/AuditStripV2';
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
}

function shortTime(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export interface ClientChannelV3Props {
  onAuthExpired?: () => void;
  showSignOut?: boolean;
}

export function ClientChannelV3({ onAuthExpired, showSignOut = false }: ClientChannelV3Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [composer, setComposer] = useState('');
  const threadRef = useRef<HTMLDivElement>(null);
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

  const handleMessage = useStreamingTurn({});
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

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!composer.trim()) return;
    emitClientTurn(composer.trim());
    setComposer('');
  };

  useEffect(() => {
    const el = threadRef.current;
    if (el && typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  return (
    <ErrorBoundary>
      <div className="v3-client-stage">
        <div className="v3-client-layout">
          <PersonaHeaderV3
            persona="fsi_client_liaison"
            surface="channel"
            showSignOut={showSignOut}
            showThemeToggle={false}
          />

          {/* Hero row — caption · phone · caption (the chat surface) */}
          <div className="v3-client-layout__hero">
            <div className="v3-client-caption">
              <div className="v3-client-caption__eyebrow">Client surface</div>
              <h1 className="v3-client-caption__title">Channel-native, not a portal.</h1>
              <p className="v3-client-caption__body">
                Eleanor opens WhatsApp like any morning. The Liaison agent answers FAQs,
                recognises intent shifts, and queues a hand-off to her RM. It never quotes
                positions or numbers.
              </p>
            </div>

            <div className="v3-phone">
              <div className="v3-phone__notch" />
              <div className="v3-phone__screen">
                <div className="v3-phone__statusbar">
                  <span className="fsi-mono">9:41</span>
                  <span className="fsi-mono" style={{ fontSize: 10 }}>● 5G · 96%</span>
                </div>
                <div className="v3-client-header">
                  <span>‹</span>
                  <div className="v3-client-header__avatar">FW</div>
                  <div>
                    <div className="v3-client-header__name">Your Wealth Team</div>
                    <div className="v3-client-header__status">
                      {connectionStatus === 'open' ? 'online' : connectionStatus}
                    </div>
                  </div>
                </div>
                <div ref={threadRef} className="v3-client-thread" role="log" aria-live="polite">
                  <div className="v3-client-day">TODAY</div>
                  {messages.length === 0 && (
                    <div className="v3-bubble v3-bubble--in">
                      Good morning. I can help with general questions. For positions or changes,
                      I'll loop in your RM.
                      <span className="v3-bubble__time">{shortTime(new Date().toISOString())}</span>
                    </div>
                  )}
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={m.from === 'client' ? 'v3-bubble v3-bubble--out' : 'v3-bubble v3-bubble--in'}
                    >
                      {m.text}
                      <span className="v3-bubble__time">{shortTime(m.timestamp)}</span>
                    </div>
                  ))}
                </div>
                <div className="v3-client-disclaimer">
                  ⓘ For informational purposes. Your RM makes recommendations.
                </div>
                <div className="v3-client-ctas">
                  <button
                    type="button"
                    data-variant="primary"
                    onClick={() => emitClientTurn('Please schedule a call with my RM.')}
                  >
                    📅 Schedule call
                  </button>
                  <button
                    type="button"
                    data-variant="secondary"
                    onClick={() => emitClientTurn('Please connect me with my RM.')}
                  >
                    👤 Ask my RM
                  </button>
                </div>
                <form className="v3-client-composer" onSubmit={submit}>
                  <input
                    type="text"
                    aria-label="Message"
                    placeholder="Type a message"
                    value={composer}
                    onChange={(e) => setComposer(e.target.value)}
                  />
                  <button type="submit" aria-label="Send">➤</button>
                </form>
              </div>
            </div>

            <div className="v3-client-caption">
              <div className="v3-client-caption__eyebrow">What Eleanor sees</div>
              <h1 className="v3-client-caption__title">Just a chat.</h1>
              <p className="v3-client-caption__body">
                No dashboards. No positions. No recommendations. The composer bar, a few
                canned CTAs, and a disclaimer. That's the whole surface — everything else
                is intentionally absent.
              </p>
            </div>
          </div>

          {/* Full-width trace row — architecture map + per-turn strip, like
              research's BriefPane and advisor's order path use the bottom
              of the screen for the "how it works" view. */}
          <div className="v3-client-layout__trace">
            <div className="v3-client-layout__trace-heading">
              <div className="v3-client-caption__eyebrow">Behind the scenes</div>
              <h1 className="v3-client-caption__title" style={{ marginBottom: '0.5rem' }}>
                One trust spine. Three surfaces.
              </h1>
              <p className="v3-client-caption__body">
                Eleanor sees a chat. Every turn flows through the same orchestrator, MNPI
                filter, and audit gate as Sarah's research and Marcus's order plan.
              </p>
            </div>
            <TraversalMapV3
              fallbackPersona="fsi_client_liaison"
              variant="client-simple"
              langfuseBaseUrl={langfuseBaseUrl}
            />
            <ClientTraceStripV3 />
          </div>
        </div>
        <AuditStripV2 langfuseBaseUrl={langfuseBaseUrl} />
      </div>
    </ErrorBoundary>
  );
}
