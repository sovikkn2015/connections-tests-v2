/**
 * v2 PersonaHeader — Workflow 360 branded bar with named persona, nav tabs,
 * live WebSocket dot, and user avatar.
 *
 * Wired: reads `connectionStatus` from useSessionStore for the live dot.
 * Navigation updates `?persona=` via anchor tags (no SPA router — matches
 * existing App.tsx routing pattern).
 */

import { PERSONA_TO_ROUTE, type Persona } from '../../shared/types/persona';
import { useSessionStore } from '../../shared/store/session';
import { W360Logo } from './W360Logo';

/**
 * Named-persona map — uploaded design names each persona (Sarah Chen,
 * Marcus Kerrigan, Eleanor Vance). Overridable via props for other
 * deployments (e.g. demos with different stage names).
 */
export const DEFAULT_PERSONA_NAMES: Record<Persona, { name: string; role: string; initials: string }> = {
  fsi_research: { name: 'Sarah Chen', role: 'Sr. Equity Analyst', initials: 'SC' },
  fsi_advisor: { name: 'Marcus Kerrigan', role: 'Sr. Wealth Advisor', initials: 'MK' },
  fsi_client_liaison: { name: 'Eleanor Vance', role: 'Tier-A · since 2009', initials: 'EV' },
};

const NAV: Array<{ label: string; persona: Persona }> = [
  { label: 'Research', persona: 'fsi_research' },
  { label: 'Advisor', persona: 'fsi_advisor' },
  { label: 'Liaison', persona: 'fsi_client_liaison' },
];

export type PersonaHeaderSurface = 'forensic' | 'light' | 'channel';

export interface PersonaHeaderV2Props {
  persona: Persona;
  surface?: PersonaHeaderSurface;
  personaNames?: Partial<Record<Persona, { name: string; role: string; initials: string }>>;
}

export function PersonaHeaderV2({
  persona,
  surface = 'forensic',
  personaNames,
}: PersonaHeaderV2Props) {
  const connectionStatus = useSessionStore((s) => s.connectionStatus);
  const principalName = useSessionStore((s) => s.principalName);

  // Prefer explicit override → real session name → default design name.
  const overrides = personaNames ?? {};
  const designed = DEFAULT_PERSONA_NAMES[persona];
  const override = overrides[persona];
  const displayName = override?.name ?? principalName ?? designed.name;
  const role = override?.role ?? designed.role;
  const initials = override?.initials ?? (principalName
    ? principalName.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()
    : designed.initials);

  const label = ({ fsi_research: 'Research', fsi_advisor: 'Advisor', fsi_client_liaison: 'Liaison' } as const)[persona];

  return (
    <header
      className={`v2-persona-header v2-persona-header--${surface}`}
      role="banner"
      aria-label={`Workflow 360 — ${label}`}
    >
      <div className="v2-persona-header__brand">
        <div className="v2-persona-header__logo">
          <W360Logo color={surface === 'channel' ? '#FFFFFF' : '#1B96FF'} />
          Workflow 360
        </div>
        <span className="v2-persona-header__persona">{label}</span>
        <nav className="v2-persona-header__nav" aria-label="Persona switcher">
          {NAV.map((item) => (
            <a
              key={item.persona}
              href={`?persona=${PERSONA_TO_ROUTE[item.persona]}&v2=1`}
              className={item.persona === persona ? 'is-active' : ''}
              aria-current={item.persona === persona ? 'page' : undefined}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
      <div className="v2-persona-header__user">
        <span className="live-dot" data-status={connectionStatus}>
          {connectionStatus === 'open' ? 'connected' : connectionStatus}
        </span>
        <div style={{ textAlign: 'right' }}>
          <div>{displayName}</div>
          <div className="v2-persona-header__role">{role}</div>
        </div>
        <span className="v2-persona-header__avatar" aria-hidden="true">{initials}</span>
      </div>
    </header>
  );
}
