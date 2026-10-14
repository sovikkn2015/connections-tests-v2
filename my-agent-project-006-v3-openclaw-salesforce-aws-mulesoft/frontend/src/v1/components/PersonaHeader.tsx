/**
 * SLDS global header with persona switcher. Each persona is a separate
 * runtime entry — switching navigates to `?persona=<route-key>`.
 */

import { PERSONA_LABEL, PERSONA_TO_ROUTE, type Persona } from '../../shared/types/persona';
import { useSessionStore } from '../../shared/store/session';
import { cx } from '../../shared/lib/slds';

export interface PersonaHeaderProps {
  persona: Persona;
  onSignOut?: () => void;
}

export function PersonaHeader({ persona, onSignOut }: PersonaHeaderProps) {
  const principalName = useSessionStore((s) => s.principalName);
  const connectionStatus = useSessionStore((s) => s.connectionStatus);
  const initials = (principalName ?? 'V3')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <header
      className={cx('v3-persona-header', `v3-persona-header--${persona}`)}
      role="banner"
      style={{
        background: '#032D60',
        color: '#FFFFFF',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.5rem 0.875rem',
        height: '3rem',
      }}
    >
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <strong>Workflow 360</strong>
        <span style={{ opacity: 0.8, fontSize: '0.8125rem' }}>{PERSONA_LABEL[persona]}</span>
        <nav aria-label="Persona switcher" style={{ display: 'flex', gap: '0.25rem' }}>
          {(Object.keys(PERSONA_TO_ROUTE) as Persona[]).map((p) => (
            <a
              key={p}
              href={`?persona=${PERSONA_TO_ROUTE[p]}`}
              aria-current={p === persona ? 'page' : undefined}
              style={{
                color: p === persona ? '#FFFFFF' : 'rgba(255,255,255,0.65)',
                fontSize: '0.75rem',
                padding: '0.125rem 0.5rem',
                borderRadius: '0.25rem',
                textDecoration: 'none',
                background: p === persona ? 'rgba(255,255,255,0.15)' : 'transparent',
              }}
            >
              {PERSONA_LABEL[p]}
            </a>
          ))}
        </nav>
      </div>
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <span style={{ fontSize: '0.75rem', opacity: 0.75 }} title="WebSocket state">
          ● {connectionStatus}
        </span>
        <span style={{ fontSize: '0.8125rem' }}>{principalName ?? 'Guest'}</span>
        <span
          aria-hidden="true"
          style={{
            width: '1.75rem',
            height: '1.75rem',
            borderRadius: '50%',
            background: '#1B96FF',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.6875rem',
            fontWeight: 700,
          }}
        >
          {initials}
        </span>
        {onSignOut && (
          <button
            type="button"
            onClick={onSignOut}
            className="slds-button slds-button_neutral"
            style={{ fontSize: '0.75rem', padding: '0.125rem 0.5rem' }}
          >
            Sign Out
          </button>
        )}
      </div>
    </header>
  );
}
