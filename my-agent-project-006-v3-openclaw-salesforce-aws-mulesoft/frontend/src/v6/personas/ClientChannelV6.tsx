/**
 * Client Channel V6 — Eleanor Vance's WhatsApp-native surface.
 *
 * Layout: full-bleed gradient stage → hero row (left caption + phone bezel
 * + right caption) → full-width trust spine below (not in side column).
 *
 * Phone: WhatsApp-style thread with bubbles, CTAs, composer.
 * Trust spine wraps V4's TraversalMapV4 + TimelineV4.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { PersonaHeaderV6 } from '../atoms/PersonaHeaderV6';
import { SampleQueries } from '../atoms/SampleQueries';
import type { QueryCategory } from '../atoms/SampleQueries';
import { TraversalMapV4 } from '../../v4/atoms/TraversalMapV4';
import { TimelineV4 } from '../../v4/atoms/TimelineV4';
import { AuditStripV4 } from '../../v4/atoms/AuditStripV4';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { VoiceButton } from '../../shared/components/VoiceButton';
import { useBriefStore } from '../../shared/store/brief';
import { useSessionStore } from '../../shared/store/session';

/* ── Types ──────────────────────────────────────────────────────────── */

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

const THREAD_STORAGE_KEY = 'v6-client-thread';

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
    const trimmed = messages.slice(-50);
    localStorage.setItem(THREAD_STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    /* localStorage full or unavailable */
  }
}

/* ── Sample queries ─────────────────────────────────────────────────── */

const CLIENT_QUERIES: QueryCategory[] = [
  {
    label: 'FAQ — fast answers',
    queries: [
      { text: 'What are your office hours?', hint: 'Haiku FAQ specialist — zero tools, zero MCP access. Isolation is architectural.' },
      { text: 'How do I update my contact information?', hint: 'L1 FAQ path — no vendor calls, read-only context' },
      { text: 'What is the minimum investment amount?', hint: 'Answered from knowledge base, no CRM access' },
    ],
  },
  {
    label: 'FAQ — scheduling',
    queries: [
      { text: 'Please schedule a call with my RM', hint: 'Hand-off to Marcus via queue_update event' },
      { text: 'Can I meet with my advisor next week?', hint: 'Intent classifier detects scheduling request → hand-off' },
    ],
  },
  {
    label: 'Escalation — concern',
    queries: [
      { text: 'Should I be worried about META?', narrative: true, hint: 'Haiku FAQ has zero tools and zero MCP access. Isolation is architectural, not prompt-based.' },
      { text: 'I keep seeing headlines about chip export bans. Is my portfolio affected?', hint: 'Intent shift detected → refusal + hand-off to RM' },
      { text: 'Can you tell me my current portfolio value?', hint: 'Refusal — liaison never quotes positions. Queues RM hand-off.' },
    ],
  },
  {
    label: 'Escalation — action request',
    queries: [
      { text: 'I want to sell all my NVDA shares', narrative: true, hint: 'Intent classifier detects sell intent → immediate hand-off to Marcus. Liaison never executes trades.' },
      { text: 'Please lock in my gains on META before earnings', hint: 'Action request → refusal + RM notification with context' },
    ],
  },
];

/* ── Main component ─────────────────────────────────────────────────── */

export interface ClientChannelV6Props {
  onAuthExpired?: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function ClientChannelV6({ onAuthExpired, theme, onToggleTheme }: ClientChannelV6Props) {
  const [messages, setMessages] = useState<Message[]>(loadPersistedThread);
  const [composer, setComposer] = useState('');
  const [spineOpen, setSpineOpen] = useState(true);
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

  const handleMessage = useStreamingTurn({
    // Listen for queue_update events — when the RM replies via the advisor
    // workbench, the reply arrives as an inbox queue_update. Render it as
    // an inbound RM message in the thread.
    onQueueUpdate: (ev) => {
      if (ev.queue === 'inbox' && ev.op === 'add' && ev.item) {
        const item = ev.item;
        setMessages((prev) => [
          ...prev,
          {
            id: ev.item_id ?? crypto.randomUUID(),
            from: 'rm' as const,
            name: 'Marcus (your RM)',
            text: item.subtitle ?? item.title ?? 'Your RM has replied.',
            timestamp: item.timestamp ?? new Date().toISOString(),
          },
        ]);
      }
    },
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

  useEffect(() => {
    persistThread(messages);
  }, [messages]);

  return (
    <ErrorBoundary>
      <div className="v6-client-stage" data-testid="v6-client">
        <PersonaHeaderV6 persona="fsi_client_liaison" theme={theme} onToggleTheme={onToggleTheme} />

        <div className="v6-client-hero">
          {/* Left caption */}
          <div className="v6-client-caption">
            <div className="v6-client-caption__eyebrow">Client surface</div>
            <h1 className="v6-client-caption__title">Channel-native, not a portal.</h1>
            <p className="v6-client-caption__body">
              Eleanor opens WhatsApp like she does any morning. The Client Liaison agent answers
              FAQs, recognises intent shifts, queues a hand-off to her RM, and never quotes
              positions or numbers.
            </p>
            <ul className="v6-client-caption__list">
              <li>
                <strong>FAQ tier</strong> — small, fast model. No vendor calls, read-only context.
              </li>
              <li>
                <strong>Hand-off tier</strong> — recognises intent shift, queues an alert in
                Marcus's workbench.
              </li>
              <li>
                <strong>Disclaimer is permanent</strong> — informational only; recommendations
                route through the RM.
              </li>
              <li>
                <strong>MNPI safe</strong> — same trust spine, redactions applied server-side.
              </li>
            </ul>
            <SampleQueries
              categories={CLIENT_QUERIES}
              onSelect={(text) => emitClientTurn(text)}
            />
          </div>

          {/* Phone bezel */}
          <div className="v6-phone">
            <div className="v6-phone__notch" />
            <div className="v6-phone__screen">
              <div className="v6-phone__statusbar">
                <span className="w360-mono">9:41</span>
                <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                  <span style={{ fontSize: 11 }}>●●●●● 5G</span>
                  <span style={{ fontSize: 11 }}>96%</span>
                </span>
              </div>
              <div className="v6-wa-header">
                <span className="v6-wa-header__back">‹</span>
                <div className="v6-wa-header__avatar">FSI</div>
                <div>
                  <div className="v6-wa-header__name">Your Wealth Team</div>
                  <div className="v6-wa-header__status">
                    {connectionStatus === 'open' ? 'online' : connectionStatus}
                  </div>
                </div>
                <div className="v6-wa-header__icons">
                  <span>📞</span>
                  <span>⋮</span>
                </div>
              </div>
              <div ref={threadRef} className="v6-thread" role="log" aria-live="polite">
                <div className="v6-thread__day">TODAY</div>
                {messages.length === 0 && (
                  <div className="v6-bubble v6-bubble--in">
                    Good morning, Eleanor. Markets opened mixed; Asia was choppy on chip-export
                    headlines. I'm here if you have any questions.
                    <span className="v6-bubble__time">{shortTime(new Date().toISOString())}</span>
                  </div>
                )}
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={m.from === 'client' ? 'v6-bubble v6-bubble--out' : 'v6-bubble v6-bubble--in'}
                  >
                    {m.name && <div className="v6-bubble__name">{m.name}</div>}
                    {m.text}
                    <span className="v6-bubble__time">{shortTime(m.timestamp)}</span>
                    {m.from === 'agent' && (
                      <div className="v6-bubble-actions">
                        <button
                          type="button"
                          className="v6-bubble-action v6-bubble-action--primary"
                          onClick={() => emitClientTurn('Please send me the brief.')}
                        >
                          📄 Send me the brief
                        </button>
                        <button
                          type="button"
                          className="v6-bubble-action v6-bubble-action--primary"
                          onClick={() => emitClientTurn('Please schedule a call with my RM.')}
                        >
                          📅 Schedule a call
                        </button>
                        <button
                          type="button"
                          className="v6-bubble-action v6-bubble-action--ghost"
                          onClick={() => {/* intentional no-op */}}
                        >
                          Do nothing for now
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <div className="v6-disclaimer">
                <span style={{ fontSize: 11 }}>ⓘ</span>
                <span>For informational purposes. Your RM makes recommendations.</span>
              </div>
              <div className="v6-ctas">
                <button
                  type="button"
                  className="v6-cta v6-cta--primary"
                  onClick={() => emitClientTurn('Please schedule a call with my RM.')}
                >
                  📅 Schedule call
                </button>
                <button
                  type="button"
                  className="v6-cta v6-cta--secondary"
                  onClick={() => emitClientTurn('Please connect me with my RM.')}
                >
                  👤 Ask my RM
                </button>
              </div>
              <form className="v6-wa-composer" onSubmit={submit}>
                <VoiceButton
                  onTranscript={setComposer}
                  onFinal={(text) => { setComposer(text); }}
                  style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', padding: '4px' }}
                />
                <input
                  className="v6-wa-composer__input"
                  type="text"
                  aria-label="Message"
                  placeholder="Type a message"
                  value={composer}
                  onChange={(e) => setComposer(e.target.value)}
                />
                <button className="v6-wa-composer__send" type="submit" aria-label="Send">
                  ➤
                </button>
              </form>
            </div>
          </div>

          {/* Right caption */}
          <div className="v6-client-caption">
            <div className="v6-client-caption__eyebrow">What Eleanor sees</div>
            <h1 className="v6-client-caption__title">Just a chat.</h1>
            <p className="v6-client-caption__body">
              No dashboards. No positions. No recommendations. The composer bar, a few canned
              CTAs, and a disclaimer. That's the whole surface — everything else is intentionally
              absent.
            </p>
          </div>
        </div>

        {/* Scroll indicator */}
        <div style={{ textAlign: 'center', padding: '0.5rem', color: 'var(--v6-text-secondary)', fontSize: 11 }}>
          ↓ Scroll for trust spine
        </div>

        {/* Full-width trust spine */}
        <div className="v6-client-trace">
          <div className="v6-client-trace__heading">
            <div className="v6-client-caption__eyebrow">Behind the scenes</div>
            <h1 className="v6-client-caption__title" style={{ marginBottom: '0.5rem' }}>
              One trust spine. Three surfaces.
            </h1>
            <p className="v6-client-caption__body">
              The Liaison surface looks like a chat to Eleanor — but every turn flows through
              the same orchestrator, MNPI filter, and audit gate as Sarah's research brief and
              Marcus's order plan.
            </p>
          </div>
          <div className="v6-trust-spine">
            <details
              open={spineOpen || undefined}
              onToggle={(e) => setSpineOpen((e.target as HTMLDetailsElement).open)}
              data-testid="v6-trust-spine"
            >
              <summary>
                <span>Trust spine — live</span>
              </summary>
              <div className="v6-trust-spine__content v4-root">
                <TraversalMapV4 persona="fsi_client_liaison" langfuseBaseUrl={langfuseBaseUrl} />
                <TimelineV4 persona="fsi_client_liaison" langfuseBaseUrl={langfuseBaseUrl} />
              </div>
            </details>
          </div>
        </div>

        <div className="v6-audit-wrap v4-root">
          <AuditStripV4 />
        </div>
      </div>
    </ErrorBoundary>
  );
}
