/**
 * RM Alert Queue — Narrative 3 (Risk Alert) front-end view.
 *
 * Polls `/api/inquiries?type=alert&status=open` every 10 seconds and renders
 * the result in an SLDS-styled list. Designed to drop into the advisor
 * persona surface. Uses the existing session token from the Zustand session
 * store; does NOT introduce a new API client.
 *
 * Row actions: Review / Accept RM Action / Override Auto-Send. Callers wire
 * their own handlers via props; defaults are no-ops so the component works in
 * isolation (and in tests). The caller is expected to post back to the
 * same backend through whatever RM action endpoint it uses.
 *
 * Accessibility: the polling region is marked `aria-live="polite"` so screen
 * readers announce newly-arrived alerts without interrupting. List rows are
 * semantic `<li>` elements inside a `<ul role="list">`; action controls are
 * `<button>`s. Empty state uses SLDS `slds-illustration` pattern.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSessionStore } from '../../../shared/store/session';
import { cx, sldsButton } from '../../../shared/lib/slds';

export interface AlertInquiry {
  id: string;
  ticker: string;
  concentration_pct: number;
  client_name: string;
  client_contact_id: string;
  auto_send_eligible: boolean;
  timestamp: string;
}

export interface AlertQueueProps {
  /** Polling interval in ms. Defaults to 10000. Override for tests. */
  pollIntervalMs?: number;
  /** API base URL. Defaults to `import.meta.env.VITE_API_URL ?? ''`. */
  apiBaseUrl?: string;
  /** Injectable fetch for tests. Defaults to global fetch. */
  fetchFn?: typeof fetch;
  /** Handlers for row actions. All default to no-op. */
  onReview?: (item: AlertInquiry) => void;
  onAcceptRmAction?: (item: AlertInquiry) => void;
  onOverrideAutoSend?: (item: AlertInquiry) => void;
}

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; items: ReadonlyArray<AlertInquiry> }
  | { status: 'error'; message: string };

export function AlertQueue(props: AlertQueueProps) {
  const {
    pollIntervalMs = 10_000,
    apiBaseUrl = import.meta.env.VITE_API_URL ?? '',
    fetchFn = fetch,
    onReview,
    onAcceptRmAction,
    onOverrideAutoSend,
  } = props;

  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const tokenSupplier = useSessionStore((s) => s.sessionToken);
  // Keep a stable ref to the supplier so the effect doesn't re-fire on token
  // rotation (AgentCore rotates tokens every ~15 min).
  const tokenRef = useRef<string | null>(tokenSupplier);
  tokenRef.current = tokenSupplier;

  const load = useCallback(
    async (signal: AbortSignal): Promise<void> => {
      try {
        const res = await fetchFn(
          `${apiBaseUrl}/api/inquiries?type=alert&status=open`,
          {
            headers: {
              Accept: 'application/json',
              Authorization: tokenRef.current ? `Bearer ${tokenRef.current}` : '',
            },
            signal,
          },
        );
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const body = (await res.json()) as { items?: AlertInquiry[] };
        const items: ReadonlyArray<AlertInquiry> = Array.isArray(body.items)
          ? body.items
          : [];
        setState({ status: 'ready', items });
      } catch (err) {
        if (signal.aborted) return;
        const message = err instanceof Error ? err.message : 'load failed';
        setState({ status: 'error', message });
      }
    },
    [apiBaseUrl, fetchFn],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const handle = setInterval(() => {
      void load(controller.signal);
    }, pollIntervalMs);
    return () => {
      controller.abort();
      clearInterval(handle);
    };
  }, [load, pollIntervalMs]);

  return (
    <section
      className="advisor-alert-queue"
      aria-labelledby="alert-queue-heading"
    >
      <header className="advisor-alert-queue__header">
        <span
          className="slds-icon_container slds-icon-action-alert"
          title="Risk alerts"
          aria-hidden="true"
        >
          <svg className="slds-icon slds-icon_x-small" viewBox="0 0 52 52">
            <path
              d="M26 2 L2 46 H50 Z M26 18 V34 M26 38 V42"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
          </svg>
        </span>
        <h2 id="alert-queue-heading" className="advisor-alert-queue__title">
          Risk Alerts
        </h2>
      </header>

      <div aria-live="polite" aria-busy={state.status === 'loading'}>
        {state.status === 'loading' && <AlertQueueSkeleton />}
        {state.status === 'error' && <AlertQueueError message={state.message} />}
        {state.status === 'ready' && state.items.length === 0 && <AlertQueueEmpty />}
        {state.status === 'ready' && state.items.length > 0 && (
          <AlertQueueTable
            items={state.items}
            onReview={onReview}
            onAcceptRmAction={onAcceptRmAction}
            onOverrideAutoSend={onOverrideAutoSend}
          />
        )}
      </div>
    </section>
  );
}

function AlertQueueSkeleton() {
  return (
    <div
      className="slds-is-relative"
      data-testid="alert-queue-skeleton"
      style={{ minHeight: '6rem' }}
    >
      <div className="slds-spinner_container">
        <div role="status" className="slds-spinner slds-spinner_small slds-spinner_brand">
          <span className="slds-assistive-text">Loading alerts</span>
          <div className="slds-spinner__dot-a" />
          <div className="slds-spinner__dot-b" />
        </div>
      </div>
    </div>
  );
}

function AlertQueueError({ message }: { message: string }) {
  return (
    <div
      role="alert"
      data-testid="alert-queue-error"
      className="slds-notify slds-notify_alert slds-alert_error"
    >
      <span className="slds-assistive-text">error</span>
      <h3 className="slds-text-heading_small">Could not load alerts</h3>
      <p className="slds-text-body_small">{message}</p>
    </div>
  );
}

function AlertQueueEmpty() {
  return (
    <div
      className="slds-illustration slds-illustration_small"
      data-testid="alert-queue-empty"
    >
      <p className="slds-text-body_regular slds-text-color_weak">
        No active volatility alerts
      </p>
    </div>
  );
}

interface AlertQueueTableProps {
  items: ReadonlyArray<AlertInquiry>;
  onReview?: (item: AlertInquiry) => void;
  onAcceptRmAction?: (item: AlertInquiry) => void;
  onOverrideAutoSend?: (item: AlertInquiry) => void;
}

function AlertQueueTable(p: AlertQueueTableProps) {
  return (
    <ul
      role="list"
      aria-label="Active volatility alerts"
      className="advisor-alert-queue__list"
      data-testid="alert-queue-list"
    >
      {p.items.map((item) => (
        <AlertRow
          key={item.id}
          item={item}
          onReview={p.onReview}
          onAcceptRmAction={p.onAcceptRmAction}
          onOverrideAutoSend={p.onOverrideAutoSend}
        />
      ))}
    </ul>
  );
}

interface AlertRowProps {
  item: AlertInquiry;
  onReview?: (item: AlertInquiry) => void;
  onAcceptRmAction?: (item: AlertInquiry) => void;
  onOverrideAutoSend?: (item: AlertInquiry) => void;
}

function AlertRow(p: AlertRowProps) {
  const { item } = p;
  return (
    <li
      className="advisor-alert-queue__row"
      data-testid={`alert-row-${item.id}`}
      data-ticker={item.ticker}
    >
      <div className="advisor-alert-queue__cell advisor-alert-queue__cell--ticker">
        <strong>{item.ticker}</strong>
      </div>
      <div className="advisor-alert-queue__cell">
        {item.concentration_pct.toFixed(2)}%
      </div>
      <div className="advisor-alert-queue__cell">{item.client_name}</div>
      <div className={cx('advisor-alert-queue__cell', 'advisor-alert-queue__cell--status')}>
        <span
          className={cx(
            'slds-badge',
            item.auto_send_eligible ? 'slds-theme_success' : 'slds-theme_warning',
          )}
        >
          {item.auto_send_eligible ? 'auto-send on' : 'auto-send off'}
        </span>
      </div>
      <div className="advisor-alert-queue__cell">
        <time dateTime={item.timestamp}>
          {new Date(item.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </time>
      </div>
      <div
        className="advisor-alert-queue__cell advisor-alert-queue__cell--actions"
        role="group"
        aria-label={`Actions for ${item.ticker} alert`}
      >
        <button
          type="button"
          className={sldsButton('neutral')}
          onClick={() => p.onReview?.(item)}
        >
          Review
        </button>
        <button
          type="button"
          className={sldsButton('brand')}
          onClick={() => p.onAcceptRmAction?.(item)}
        >
          Accept RM Action
        </button>
        <button
          type="button"
          className={sldsButton('destructive')}
          onClick={() => p.onOverrideAutoSend?.(item)}
        >
          Override Auto-Send
        </button>
      </div>
    </li>
  );
}
