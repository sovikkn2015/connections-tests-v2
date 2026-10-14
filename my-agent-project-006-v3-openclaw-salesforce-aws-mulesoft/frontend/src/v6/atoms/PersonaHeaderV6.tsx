/**
 * V6 Persona Header — SLDS-inspired 44px bar with brand, nav, user, and
 * light/dark theme toggle.
 *
 * CRITICAL: All nav links use `&v6=1` so persona switching stays in V6.
 * This was broken in V4/V5 where clicking Advisor from Research went to
 * `&v4=1`. Every `<a>` href here includes `v6=1`.
 *
 * Theme toggle persists to localStorage key `v6.theme` and applies
 * `data-theme` on the document root element.
 */

import { useSessionStore } from '../../shared/store/session';
import { PERSONA_TO_ROUTE, type Persona } from '../../shared/types/persona';

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

export interface PersonaHeaderV6Props {
  persona: Persona;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function PersonaHeaderV6({ persona, theme, onToggleTheme }: PersonaHeaderV6Props) {
  const connectionStatus = useSessionStore((s) => s.connectionStatus);
  const principalName = useSessionStore((s) => s.principalName);
  const principalId = useSessionStore((s) => s.principalId);

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
    <header className="v6-header" role="banner">
      <div className="v6-header__brand">
        <div className="v6-header__logo">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5" />
            <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          FSI Workforce 360
        </div>
        <nav className="v6-header__nav" aria-label="Persona switcher">
          {NAV.map((item) => (
            <a
              key={item.persona}
              href={`?persona=${PERSONA_TO_ROUTE[item.persona]}&v6=1`}
              className={item.persona === persona ? 'is-active' : ''}
              aria-current={item.persona === persona ? 'page' : undefined}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
      <div className="v6-header__right">
        <span className="v6-header__status" data-status={connectionStatus}>
          ● {connectionStatus === 'open' ? 'connected' : connectionStatus}
        </span>
        <span className="v6-header__user">
          {name} · <span className="v6-header__user-role">{role}</span>
        </span>
        <span className="v6-header__avatar" aria-hidden="true">
          {initials}
        </span>
        <button
          type="button"
          className="v6-header__theme-btn"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-pressed={theme === 'light'}
          data-testid="v6-theme-toggle"
        >
          {theme === 'dark' ? '☾' : '☀'}
        </button>
      </div>
    </header>
  );
}
