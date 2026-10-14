/**
 * Salesforce-style global header.
 * Blue (#0070d2) background, white text, app name + user avatar.
 */

import { useAgentStore } from '../store/agentStore';
import { useAuth } from '../App';

export default function GlobalHeader() {
  const { userInfo } = useAgentStore();
  const auth = useAuth();

  const initials = userInfo?.name
    ? userInfo.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'A';

  return (
    <header
      className="slds-global-header_container"
      style={{ background: '#0070d2', height: '2.5rem' }}
    >
      <div
        className="slds-global-header slds-grid slds-grid_align-spread slds-grid_vertical-align-center"
        style={{
          background: '#0070d2',
          height: '2.5rem',
          padding: '0 1rem',
        }}
      >
        {/* Left: App name */}
        <div className="slds-global-header__item">
          <span
            className="slds-text-heading_small"
            style={{ color: '#ffffff', fontWeight: 700, letterSpacing: '0.025em' }}
          >
            005 IR Research Workbench
          </span>
        </div>

        {/* Right: User info + logout */}
        <div className="slds-global-header__item slds-grid slds-grid_vertical-align-center">
          {userInfo && (
            <span
              className="slds-m-right_small slds-text-body_small"
              style={{ color: '#ffffff' }}
            >
              {userInfo.name}
            </span>
          )}
          <span
            className="slds-avatar slds-avatar_circle slds-avatar_x-small"
            style={{
              background: '#ffffff',
              color: '#0070d2',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.625rem',
              width: '1.5rem',
              height: '1.5rem',
              borderRadius: '50%',
            }}
            aria-label={userInfo?.name ?? 'User avatar'}
          >
            {initials}
          </span>
          {auth && (
            <button
              className="slds-button slds-m-left_small"
              style={{ color: '#ffffff', fontSize: '0.75rem' }}
              onClick={auth.logOut}
              aria-label="Sign out"
            >
              Sign Out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
