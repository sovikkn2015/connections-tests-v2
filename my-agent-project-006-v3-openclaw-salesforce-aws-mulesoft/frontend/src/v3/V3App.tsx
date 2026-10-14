/**
 * V3App — v3 persona router wrapped in FSI Workforce 360 branding.
 *
 * Activation: `?v3=1` or `?ui=v3`. Supersedes v2 UI when set.
 *
 * Auth:
 *   - If Cognito env vars are present AND VITE_AUTH_DEV_BOOTSTRAP != 1:
 *     the SPA tries to load an existing Cognito session from
 *     localStorage. If none, redirects to Cognito hosted UI.
 *   - Otherwise: uses the dev-bootstrap-token flow inherited from v2
 *     (the shared session store already has that logic via App.tsx).
 *
 * Routing:
 *   - /auth/callback → AuthCallback component (PKCE code exchange)
 *   - ?persona=research → ResearchTerminalV3
 *   - ?persona=advisor  → AdvisorWorkbenchV3
 *   - ?persona=client   → ClientChannelV3
 */

import { useEffect, useMemo, useState } from 'react';
import { ResearchTerminalV3 } from './personas/ResearchTerminalV3';
import { AdvisorWorkbenchV3 } from './personas/AdvisorWorkbenchV3';
import { ClientChannelV3 } from './personas/ClientChannelV3';
import { AuthCallback } from './auth/AuthCallback';
import {
  loadSession,
  readConfigFromEnv,
  shouldUseCognito,
  startLogin,
} from './auth/cognito';
import { useTheme } from './theme/useTheme';
import { RestClient } from '../shared/lib/restClient';
import { useSessionStore } from '../shared/store/session';
import { personaFromRoute } from '../shared/types/persona';

import './styles/tokens.css';
import './styles/header.css';
import './styles/map.css';
import './styles/personas.css';
// v3 personas re-use v2 atoms (TimelineV2, AuditStripV2, InlineActionCard,
// GatesTrackerV2) which scope their CSS under `.v2-root`. v3 atoms under
// `.v3-root` need the v2 styles too, so we pull them in here and scope-
// override via `.v3-root .v2-...` selectors where needed.
import '../v2/styles/tokens.css';
import '../v2/styles/gates.css';
import '../v2/styles/map.css';
import '../v2/styles/timeline.css';
import '../v2/styles/personas.css';

export interface V3AppProps {
  onAuthExpired?: () => void;
}

type AuthPhase = 'pending' | 'ready' | 'needs_login';

export function V3App({ onAuthExpired }: V3AppProps) {
  const [phase, setPhase] = useState<AuthPhase>('pending');
  // Initialise theme up front so the data-theme attribute is set before
  // any v3 component renders. The hook both reads localStorage and
  // mirrors the value into the DOM.
  useTheme();
  const apiUrl = (import.meta.env.VITE_API_URL ?? '') as string;
  const rest = useMemo(
    () => new RestClient(apiUrl, () => useSessionStore.getState().sessionToken ?? ''),
    [apiUrl],
  );

  // Path-based mini-router — only handles /auth/callback. Everything else
  // is query-string driven and delegates to the persona switcher below.
  const path =
    typeof window !== 'undefined' ? window.location.pathname : '/';
  const isAuthCallback = path === '/auth/callback' || path.endsWith('/auth/callback');

  useEffect(() => {
    if (isAuthCallback) {
      // AuthCallback handles its own session write — nothing to do here.
      setPhase('ready');
      return;
    }

    const session = useSessionStore.getState();
    if (session.sessionToken) {
      // Session already set (either dev bootstrap from App.tsx OR restored
      // from localStorage below).
      setPhase('ready');
      return;
    }

    if (shouldUseCognito()) {
      // Try to restore Cognito session from localStorage.
      const cached = loadSession();
      if (cached) {
        session.setAuth({
          sessionToken: cached.accessToken,
          principalId: cached.principalId,
          principalName: cached.principalName,
          sessionId: crypto.randomUUID(),
          correlationId: crypto.randomUUID(),
        });
        setPhase('ready');
      } else {
        // No session — kick off Cognito login.
        setPhase('needs_login');
      }
    } else {
      // Dev bootstrap path (ran in App.tsx before we got here). If we
      // reach this branch without a session it means dev bootstrap was
      // disabled — degrade to "pending" state with a human-readable
      // placeholder rather than a hard redirect.
      setPhase('ready');
    }
  }, [isAuthCallback]);

  if (isAuthCallback) {
    return (
      <div className="v3-root">
        <AuthCallback />
      </div>
    );
  }

  if (phase === 'pending') {
    return (
      <div className="v3-root">
        <div
          role="status"
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--forensic-bg-2)',
            color: 'var(--forensic-text-1)',
            fontFamily: 'Inter, system-ui, sans-serif',
          }}
        >
          Loading…
        </div>
      </div>
    );
  }

  if (phase === 'needs_login') {
    const cfg = readConfigFromEnv();
    return (
      <div className="v3-root">
        <div
          role="main"
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--forensic-bg-2)',
            color: 'var(--forensic-text-1)',
            fontFamily: 'Inter, system-ui, sans-serif',
            flexDirection: 'column',
            gap: '1.5rem',
            padding: '2rem',
          }}
        >
          <div style={{ textAlign: 'center', maxWidth: 480 }}>
            <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
              FSI Workforce 360
            </div>
            <div style={{ fontSize: 13, opacity: 0.75, marginBottom: 24 }}>
              {cfg
                ? 'Sign in with Cognito to continue.'
                : 'No authentication configured.'}
            </div>
            {cfg && (
              <button
                type="button"
                onClick={() => startLogin()}
                style={{
                  padding: '0.75rem 1.75rem',
                  background: '#1B96FF',
                  color: '#FFFFFF',
                  border: 0,
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                Sign in with Cognito
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const persona =
    typeof window !== 'undefined'
      ? personaFromRoute(new URLSearchParams(window.location.search).get('persona'))
      : 'fsi_research';

  const showSignOut = shouldUseCognito();

  return (
    <div className="v3-root v2-root" data-testid="v3-root">
      {persona === 'fsi_research' && (
        <ResearchTerminalV3
          rest={rest}
          onAuthExpired={onAuthExpired}
          showSignOut={showSignOut}
        />
      )}
      {persona === 'fsi_advisor' && (
        <AdvisorWorkbenchV3 onAuthExpired={onAuthExpired} showSignOut={showSignOut} />
      )}
      {persona === 'fsi_client_liaison' && (
        <ClientChannelV3 onAuthExpired={onAuthExpired} showSignOut={showSignOut} />
      )}
    </div>
  );
}
