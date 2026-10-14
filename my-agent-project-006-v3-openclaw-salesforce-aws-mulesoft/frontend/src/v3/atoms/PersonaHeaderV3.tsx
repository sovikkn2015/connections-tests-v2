/**
 * v3 PersonaHeader — FSI Workforce 360 branded bar.
 *
 * Rename: Workflow 360 → FSI Workforce 360 (roadmap item #6).
 * Adds: optional sign-out button (roadmap item #3, Cognito).
 * Adds: optional theme toggle button (roadmap item #5, light/dark mode).
 */

import { PERSONA_TO_ROUTE, type Persona } from '../../shared/types/persona';
import { useSessionStore } from '../../shared/store/session';
import { FsiLogo } from './FsiLogo';
import { clearSession } from '../auth/cognito';
import { useTheme } from '../theme/useTheme';

export const DEFAULT_PERSONA_NAMES: Record<
  Persona,
  { name: string; role: string; initials: string }
> = {
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

export interface PersonaHeaderV3Props {
  persona: Persona;
  surface?: PersonaHeaderSurface;
  personaNames?: Partial<Record<Persona, { name: string; role: string; initials: string }>>;
  showSignOut?: boolean;
  /** Show the dark/light theme toggle button. Defaults to true. Pass
   * `false` on the channel surface where it would clash with the green
   * WhatsApp header. */
  showThemeToggle?: boolean;
}

export function PersonaHeaderV3({
  persona,
  surface = 'forensic',
  personaNames,
  showSignOut = false,
  showThemeToggle = true,
}: PersonaHeaderV3Props) {
  const connectionStatus = useSessionStore((s) => s.connectionStatus);
  const principalName = useSessionStore((s) => s.principalName);
  const principalId = useSessionStore((s) => s.principalId);
  const { theme, toggle: toggleTheme } = useTheme();

  // Dev bootstrap (principalId === 'dev-principal') mints a generic
  // 'Dev User' name; combined with the persona's role string that
  // produced 'Dev User · Tier-A · since 2009' for Eleanor's view, which
  // mixes registers. In dev bootstrap fall back to the designed persona
  // identity; real sessions show the authenticated user.
  const isDevBootstrap = principalId === 'dev-principal';
  const overrides = personaNames ?? {};
  const designed = DEFAULT_PERSONA_NAMES[persona];
  const override = overrides[persona];
  const displayName =
    override?.name ?? (!isDevBootstrap && principalName ? principalName : designed.name);
  const role = override?.role ?? designed.role;
  const initials =
    override?.initials ??
    (!isDevBootstrap && principalName
      ? principalName
          .split(' ')
          .map((n) => n[0])
          .join('')
          .slice(0, 2)
          .toUpperCase()
      : designed.initials);

  const label = (
    {
      fsi_research: 'Research',
      fsi_advisor: 'Advisor',
      fsi_client_liaison: 'Liaison',
    } as const
  )[persona];

  const handleSignOut = () => {
    clearSession();
    useSessionStore.getState().clearAuth();
    window.location.replace('/');
  };

  return (
    <header
      className={`v3-persona-header v3-persona-header--${surface}`}
      role="banner"
      aria-label={`FSI Workforce 360 — ${label}`}
    >
      <div className="v3-persona-header__brand">
        <div className="v3-persona-header__logo">
          <FsiLogo color={surface === 'channel' ? '#FFFFFF' : '#1B96FF'} />
          FSI Workforce 360
        </div>
        <nav className="v3-persona-header__nav" aria-label="Persona switcher">
          {NAV.map((item) => (
            <a
              key={item.persona}
              href={`?persona=${PERSONA_TO_ROUTE[item.persona]}&v3=1`}
              className={item.persona === persona ? 'is-active' : ''}
              aria-current={item.persona === persona ? 'page' : undefined}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
      <div className="v3-persona-header__user">
        <span className="v3-live-dot" data-status={connectionStatus}>
          {connectionStatus === 'open' ? 'connected' : connectionStatus}
        </span>
        <div style={{ textAlign: 'right' }}>
          <div>{displayName}</div>
          <div className="v3-persona-header__role">{role}</div>
        </div>
        <span className="v3-persona-header__avatar" aria-hidden="true">
          {initials}
        </span>
        {showThemeToggle && (
          <button
            type="button"
            className="v3-persona-header__theme"
            onClick={toggleTheme}
            title={
              theme === 'dark'
                ? 'Switch to light theme'
                : 'Switch to dark theme'
            }
            aria-label={
              theme === 'dark'
                ? 'Switch to light theme'
                : 'Switch to dark theme'
            }
            aria-pressed={theme === 'light'}
            data-testid="v3-theme-toggle"
          >
            {theme === 'dark' ? '☾' : '☀'}
          </button>
        )}
        {showSignOut && (
          <button
            type="button"
            className="v3-persona-header__signout"
            onClick={handleSignOut}
            title="Sign out and clear Cognito session"
          >
            Sign out
          </button>
        )}
      </div>
    </header>
  );
}
