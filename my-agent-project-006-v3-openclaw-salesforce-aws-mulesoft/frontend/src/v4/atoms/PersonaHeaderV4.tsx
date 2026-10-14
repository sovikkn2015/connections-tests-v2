/**
 * V4 persona header — 44px bar, brand + nav + user.
 *
 * Verbatim port of the uploaded design's PersonaHeader. Reads live
 * session state (principalName, connectionStatus) from the shared
 * Zustand store — so the "connected" live-dot and "Sarah Chen · Sr.
 * Equity Analyst" user block reflect actual auth state, not hardcoded
 * strings.
 */

import { useSessionStore } from '../../shared/store/session';
import { PERSONA_TO_ROUTE, type Persona } from '../../shared/types/persona';
import { useTheme } from '../theme/useTheme';
import { W360Logo } from './W360Logo';

const NAV: Array<{ label: string; persona: Persona }> = [
  { label: 'Research', persona: 'fsi_research' },
  { label: 'Advisor', persona: 'fsi_advisor' },
  { label: 'Liaison', persona: 'fsi_client_liaison' },
];

const DEFAULT_IDENTITY: Record<Persona, { name: string; role: string; initials: string }> = {
  fsi_research: { name: 'Sarah Chen', role: 'Sr. Equity Analyst', initials: 'SC' },
  fsi_advisor: { name: 'Marcus Kerrigan', role: 'Sr. Wealth Advisor', initials: 'MK' },
  fsi_client_liaison: { name: 'Eleanor Vance', role: 'Tier-A · since 2009', initials: 'EV' },
};

export interface PersonaHeaderV4Props {
  persona: Persona;
}

export function PersonaHeaderV4({ persona }: PersonaHeaderV4Props) {
  const connectionStatus = useSessionStore((s) => s.connectionStatus);
  const principalName = useSessionStore((s) => s.principalName);
  const { theme, toggle: toggleTheme } = useTheme();
  const principalId = useSessionStore((s) => s.principalId);

  // When the app uses the dev bootstrap (principalId === 'dev-principal'),
  // the session name is a generic 'Dev User' — showing it next to the
  // designed persona role ('Sarah · Sr. Equity Analyst') produced the
  // confusing 'Dev User · Tier-A · since 2009' in earlier builds.
  // In dev bootstrap, always fall back to the designed identity so the
  // header tells the same story as the rest of the UI. Real sessions
  // (Cognito) still show the signed-in user.
  const isDevBootstrap = principalId === 'dev-principal';
  const designed = DEFAULT_IDENTITY[persona];
  const name = !isDevBootstrap && principalName ? principalName : designed.name;
  const role = designed.role;
  const initials =
    !isDevBootstrap && principalName
      ? principalName
          .split(' ')
          .map((n) => n[0])
          .join('')
          .slice(0, 2)
          .toUpperCase()
      : designed.initials;

  return (
    <header className="persona-header" role="banner">
      <div className="persona-header__brand">
        <div className="persona-header__logo">
          <W360Logo />
          FSI Workforce 360
        </div>
        <nav className="persona-header__nav" aria-label="Persona switcher">
          {NAV.map((item) => (
            <a
              key={item.persona}
              href={`?persona=${PERSONA_TO_ROUTE[item.persona]}&v4=1`}
              className={item.persona === persona ? 'is-active' : ''}
              aria-current={item.persona === persona ? 'page' : undefined}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
      <div className="persona-header__user">
        <span className="live-dot" data-status={connectionStatus}>
          {connectionStatus === 'open' ? 'connected' : connectionStatus}
        </span>
        <span style={{ color: 'rgba(255,255,255,0.7)' }}>
          {name} · <span style={{ opacity: 0.7 }}>{role}</span>
        </span>
        <span className="persona-header__avatar" aria-hidden="true">
          {initials}
        </span>
        <button
          type="button"
          className="persona-header__theme"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-pressed={theme === 'light'}
          data-testid="v4-theme-toggle"
        >
          {theme === 'dark' ? '☾' : '☀'}
        </button>
      </div>
    </header>
  );
}
