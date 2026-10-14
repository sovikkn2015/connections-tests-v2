/**
 * Salesforce Lightning Experience global header.
 * Matches the real SF global header: dark navy (#032D60) background,
 * waffle icon, app name, search bar, user avatar with dropdown.
 * Uses exact SLDS color tokens and spacing.
 */

import { useAgentStore } from '../store/agentStore';
import { useAuth } from '../App';

export default function GlobalHeader() {
  const { userInfo } = useAgentStore();
  const auth = useAuth();

  const initials = userInfo?.name
    ? userInfo.name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : 'WA';

  return (
    <header className="wa-global-header" role="banner">
      <div className="wa-global-header__inner">
        {/* Left: Waffle + App Launcher */}
        <div className="wa-global-header__left">
          <button className="wa-waffle-btn" aria-label="App Launcher" title="App Launcher">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <circle cx="4" cy="4" r="2" fill="#ffffff" />
              <circle cx="10" cy="4" r="2" fill="#ffffff" />
              <circle cx="16" cy="4" r="2" fill="#ffffff" />
              <circle cx="4" cy="10" r="2" fill="#ffffff" />
              <circle cx="10" cy="10" r="2" fill="#ffffff" />
              <circle cx="16" cy="10" r="2" fill="#ffffff" />
              <circle cx="4" cy="16" r="2" fill="#ffffff" />
              <circle cx="10" cy="16" r="2" fill="#ffffff" />
              <circle cx="16" cy="16" r="2" fill="#ffffff" />
            </svg>
          </button>
          <div className="wa-app-name">
            <svg className="wa-cloud-icon" width="22" height="16" viewBox="0 0 24 18" fill="none" aria-hidden="true">
              <path d="M19.35 6.04C18.67 2.59 15.64 0 12 0 9.11 0 6.6 1.64 5.35 4.04 2.34 4.36 0 6.91 0 10c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z" fill="#ffffff" opacity="0.9"/>
            </svg>
            <span className="wa-app-name__text">Wealth Advisor</span>
          </div>
          <nav className="wa-header-nav" aria-label="Primary navigation">
            <span className="wa-header-nav__item wa-header-nav__item--active">Home</span>
            <span className="wa-header-nav__item">Clients</span>
            <span className="wa-header-nav__item">Portfolios</span>
            <span className="wa-header-nav__item">Reports</span>
          </nav>
        </div>
        <div className="wa-global-header__right">
          {userInfo && <span className="wa-user-name">{userInfo.name}</span>}
          <span className="wa-avatar" aria-label={userInfo?.name ?? 'User avatar'}>{initials}</span>
          {auth && (
            <button className="wa-signout-btn" onClick={auth.logOut} aria-label="Sign out">
              Sign Out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
