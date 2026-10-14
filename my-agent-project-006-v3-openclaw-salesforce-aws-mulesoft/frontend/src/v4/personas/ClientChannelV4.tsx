/**
 * Client Channel V4 — Eleanor Vance's WhatsApp-native surface.
 *
 * Layout matches research + advisor: hero row on top (left caption,
 * centered phone bezel, right caption), then a FULL-WIDTH trust-spine
 * row BELOW with the architecture map stacked over the timeline.
 * Earlier V4 crammed the trust spine into the right-side caption column
 * which squashed both the map and the timeline — fixed by lifting them
 * into their own full-width row, same pattern as the other two
 * personas.
 *
 * Live wiring is unchanged:
 *  - Composer send fires `useAgentSocket({ type: 'turn' })`
 *  - Thread mirrors local + agent turns; brief text pours into the most
 *    recent in-bubble when complete
 *  - TrustSpineV4 is the same collapsible atom research + advisor use,
 *    so the visual rhythm is consistent across all three personas.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { TrustSpineV4 } from '../atoms/TrustSpineV4';
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

export interface ClientChannelV4Props {
  onAuthExpired?: () => void;
}

const THREAD_STORAGE_KEY = 'v4-client-thread';

function loadPersistedThread(): Message[] {
  try {
    const raw = localStorage.getItem(THREAD_STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as Message[];
  } catch {
    return [];
  }
}

function persistThread(messages: Message[]) {
  try {
    // Keep last 50 messages to avoid localStorage bloat
    const trimmed = messages.slice(-50);
    localStorage.setItem(THREAD_STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    /* localStorage full or unavailable — degrade silently */
  }
}

export function ClientChannelV4({ onAuthExpired }: ClientChannelV4Props) {
  const [messages, setMessages] = useState<Message[]>(loadPersistedThread);
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

  // Persist thread to localStorage on every change
  useEffect(() => {
    persistThread(messages);
  }, [messages]);

  return (
    <ErrorBoundary>
      <div className="client-stage" data-testid="v4-client">
        <div className="client-layout">
          {/* Hero row — left caption · phone · right caption */}
          <div className="client-layout__hero">
            <div className="client-grid__caption">
              <div className="client-grid__caption-eyebrow">Client surface</div>
              <h1 className="client-grid__caption-title">Channel-native, not a portal.</h1>
              <p className="client-grid__caption-body">
                Eleanor opens WhatsApp like she does any morning. The Client Liaison agent answers
                FAQs, recognises intent shifts, queues a hand-off to her RM, and never quotes
                positions or numbers.
              </p>
              <ul className="client-grid__caption-list">
                <li>
                  <span>
                    <strong>FAQ tier</strong> — small, fast model. No vendor calls, read-only
                    context.
                  </span>
                </li>
                <li>
                  <span>
                    <strong>Hand-off tier</strong> — recognises intent shift, queues an alert in
                    Marcus's workbench.
                  </span>
                </li>
                <li>
                  <span>
                    <strong>Disclaimer is permanent</strong> — informational only;
                    recommendations route through the RM.
                  </span>
                </li>
                <li>
                  <span>
                    <strong>MNPI safe</strong> — same trust spine, redactions applied server-side.
                  </span>
                </li>
              </ul>
            </div>

            <div className="phone">
              <div className="phone__notch" />
              <div className="phone__screen">
                <div className="phone__statusbar">
                  <span className="w360-mono">9:41</span>
                  <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                    <span style={{ fontSize: 11 }}>●●●●● 5G</span>
                    <span style={{ fontSize: 11 }}>96%</span>
                  </span>
                </div>
                <div className="client-header">
                  <span className="client-header__back">‹</span>
                  <div className="client-header__avatar">FSI</div>
                  <div>
                    <div className="client-header__name">Your Wealth Team</div>
                    <div className="client-header__status">
                      {connectionStatus === 'open' ? 'online' : connectionStatus}
                    </div>
                  </div>
                  <div className="client-header__icons">
                    <span>📞</span>
                    <span>⋮</span>
                  </div>
                </div>
                <div
                  ref={threadRef}
                  className="client-thread"
                  role="log"
                  aria-live="polite"
                >
                  <div className="client-day">TODAY</div>
                  {messages.length === 0 && (
                    <div className="bubble bubble--in">
                      Good morning, Eleanor. Markets opened mixed; Asia was choppy on chip-export
                      headlines. I'm here if you have any questions.
                      <span className="bubble__time">{shortTime(new Date().toISOString())}</span>
                    </div>
                  )}
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={m.from === 'client' ? 'bubble bubble--out' : 'bubble bubble--in'}
                    >
                      {m.name && <div className="bubble__name">{m.name}</div>}
                      {m.text}
                      <span
                        className={
                          'bubble__time' + (m.from === 'client' ? ' bubble__time--out' : '')
                        }
                      >
                        {shortTime(m.timestamp)}
                      </span>
                      {/* Per-message action buttons for agent replies (Act 1 script requirement) */}
                      {m.from === 'agent' && (
                        <div style={{
                          display: 'flex',
                          gap: 6,
                          marginTop: 8,
                          flexWrap: 'wrap',
                        }}>
                          <button
                            type="button"
                            style={{
                              fontSize: 11,
                              padding: '4px 10px',
                              borderRadius: 12,
                              border: '1px solid rgba(37,211,102,0.4)',
                              background: 'rgba(37,211,102,0.08)',
                              color: '#25d366',
                              cursor: 'pointer',
                            }}
                            onClick={() => emitClientTurn('Please send me the brief.')}
                          >
                            📄 Send me the brief
                          </button>
                          <button
                            type="button"
                            style={{
                              fontSize: 11,
                              padding: '4px 10px',
                              borderRadius: 12,
                              border: '1px solid rgba(37,211,102,0.4)',
                              background: 'rgba(37,211,102,0.08)',
                              color: '#25d366',
                              cursor: 'pointer',
                            }}
                            onClick={() => emitClientTurn('Please schedule a call with my RM.')}
                          >
                            📅 Schedule a call
                          </button>
                          <button
                            type="button"
                            style={{
                              fontSize: 11,
                              padding: '4px 10px',
                              borderRadius: 12,
                              border: '1px solid rgba(100,100,100,0.4)',
                              background: 'transparent',
                              color: '#999',
                              cursor: 'pointer',
                            }}
                            onClick={() => {/* do nothing — intentional */}}
                          >
                            Do nothing for now
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <div className="client-disclaimer">
                  <span style={{ fontSize: 11 }}>ⓘ</span>
                  <span>For informational purposes. Your RM makes recommendations.</span>
                </div>
                <div className="client-ctas">
                  <button
                    type="button"
                    className="cta--primary"
                    onClick={() => emitClientTurn('Please schedule a call with my RM.')}
                  >
                    📅 Schedule call
                  </button>
                  <button
                    type="button"
                    className="cta--secondary"
                    onClick={() => emitClientTurn('Please connect me with my RM.')}
                  >
                    👤 Ask my RM
                  </button>
                </div>
                <form className="client-composer" onSubmit={submit}>
                  <span style={{ color: '#999', fontSize: 18, paddingLeft: 4 }}>☺</span>
                  <input
                    className="client-composer__input"
                    type="text"
                    aria-label="Message"
                    placeholder="Type a message"
                    value={composer}
                    onChange={(e) => setComposer(e.target.value)}
                  />
                  <button
                    className="client-composer__send"
                    type="submit"
                    aria-label="Send"
                  >
                    ➤
                  </button>
                </form>
              </div>
            </div>

            <div className="client-grid__caption">
              <div className="client-grid__caption-eyebrow">What Eleanor sees</div>
              <h1 className="client-grid__caption-title">Just a chat.</h1>
              <p className="client-grid__caption-body">
                No dashboards. No positions. No recommendations. The composer bar, a few canned
                CTAs, and a disclaimer. That's the whole surface — everything else is intentionally
                absent.
              </p>
            </div>
          </div>

          {/* Full-width trust-spine row — matches research + advisor layout.
              Uses the same collapsible atom so the visual rhythm is
              consistent across all three personas. */}
          <div className="client-layout__trace">
            <div className="client-layout__trace-heading">
              <div className="client-grid__caption-eyebrow">Behind the scenes</div>
              <h1 className="client-grid__caption-title" style={{ marginBottom: '0.5rem' }}>
                One trust spine. Three surfaces.
              </h1>
              <p className="client-grid__caption-body">
                The Liaison surface looks like a chat to Eleanor — but every turn flows through
                the same orchestrator, MNPI filter, and audit gate as Sarah's research brief and
                Marcus's order plan.
              </p>
            </div>
            <TrustSpineV4 persona="fsi_client_liaison" langfuseBaseUrl={langfuseBaseUrl} />
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}
