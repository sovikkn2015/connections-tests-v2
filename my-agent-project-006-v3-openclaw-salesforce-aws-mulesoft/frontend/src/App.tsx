/**
 * Root router.
 *
 * Chooses between v1, v2, v3, v4, v5, and v6 based on query-string flags,
 * then delegates to the matching *App. Everything shared (auth bootstrap,
 * session store, react-query provider) lives here so all variants
 * consume the same singleton.
 *
 * Auth:
 *   When Cognito env vars are present AND VITE_AUTH_DEV_BOOTSTRAP != 1,
 *   the root App gates ALL variants behind Cognito hosted UI login.
 *   This means v3, v4, v5, v6 all get real auth without any per-variant
 *   code. The Cognito session is written to the shared session store
 *   before any *App renders.
 *
 *   When Cognito is not configured (or dev bootstrap is on), the old
 *   dev-bootstrap-token flow runs — same as before.
 *
 * Routing rules (first match wins):
 *   - `?v6=1` or `?ui=v6`          → V6App (explicit)
 *   - `?v5=1` or `?ui=v5`          → V5App
 *   - `?v4=1` or `?ui=v4`          → V4App
 *   - `?v3=1` or `/auth/callback`  → V3App
 *   - `?v2=1` or `?ui=v2`          → V2App
 *   - `?v1=1` or `?ui=v1`          → V1App (explicit legacy)
 *   - otherwise                    → V6App (default — recommended)
 *
 * Persona selection (`?persona=research|advisor|client`) is handled
 * inside each *App since they may want different defaults or routes
 * (e.g. v1's `?view=alerts` alternate advisor view).
 */

import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { V1App } from './v1/V1App';
import { V2App } from './v2/V2App';
import { V3App } from './v3/V3App';
import { V4App } from './v4/V4App';
import { V5App } from './v5/V5App';
import { V6App } from './v6/V6App';
import { AuthCallback } from './v3/auth/AuthCallback';
import {
  loadSession,
  readConfigFromEnv,
  shouldUseCognito,
  startLogin,
} from './v3/auth/cognito';
import { useSessionStore } from './shared/store/session';
import { personaFromRoute } from './shared/types/persona';

const qc = new QueryClient();

function useUrlPersona() {
  const setPersona = useSessionStore((s) => s.setPersona);
  const current = useSessionStore((s) => s.persona);
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('persona');
    const next = personaFromRoute(raw);
    if (next !== current) setPersona(next);
  }, [current, setPersona]);
  return current;
}

function ensureDevSession(): void {
  const session = useSessionStore.getState();
  if (session.sessionToken) return;
  session.setAuth({
    sessionToken: 'dev-bootstrap-token',
    principalId: 'dev-principal',
    principalName: 'Dev User',
    sessionId: crypto.randomUUID(),
    correlationId: crypto.randomUUID(),
  });
}

function handleAuthExpired(): void {
  useSessionStore.getState().clearAuth();
  if (shouldUseCognito()) {
    startLogin().catch(() => {
      // If startLogin fails (e.g. popup blocked), clear and let the gate re-render.
    });
  }
}

type AuthPhase = 'pending' | 'ready' | 'needs_login';

export default function App() {
  const [authPhase, setAuthPhase] = useState<AuthPhase>('pending');
  useUrlPersona();

  const path = typeof window !== 'undefined' ? window.location.pathname : '/';
  const isAuthCallback = path === '/auth/callback' || path.endsWith('/auth/callback');

  // -----------------------------------------------------------------------
  // Auth bootstrap — runs once on mount. Three paths:
  //   1. Auth callback (/auth/callback) → let AuthCallback handle it
  //   2. Cognito configured → restore session or redirect to hosted UI
  //   3. Dev bootstrap → mint dev-bootstrap-token
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (isAuthCallback) {
      setAuthPhase('ready');
      return;
    }

    const store = useSessionStore.getState();
    if (store.sessionToken) {
      setAuthPhase('ready');
      return;
    }

    if (shouldUseCognito()) {
      const cached = loadSession();
      if (cached) {
        store.setAuth({
          sessionToken: cached.accessToken,
          principalId: cached.principalId,
          principalName: cached.principalName,
          sessionId: crypto.randomUUID(),
          correlationId: crypto.randomUUID(),
        });
        setAuthPhase('ready');
      } else {
        setAuthPhase('needs_login');
      }
    } else {
      // Dev bootstrap
      ensureDevSession();
      setAuthPhase('ready');
    }
  }, [isAuthCallback]);

  // -----------------------------------------------------------------------
  // Auth callback route — shared across all variants
  // -----------------------------------------------------------------------
  if (isAuthCallback) {
    return (
      <QueryClientProvider client={qc}>
        <AuthCallback />
      </QueryClientProvider>
    );
  }

  // -----------------------------------------------------------------------
  // Cognito login gate — shown when no session and Cognito is configured
  // -----------------------------------------------------------------------
  if (authPhase === 'pending') {
    return (
      <div
        role="status"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0B1B2F',
          color: '#E6EDF3',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        Loading…
      </div>
    );
  }

  if (authPhase === 'needs_login') {
    const cfg = readConfigFromEnv();
    return (
      <div
        role="main"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0B1B2F',
          color: '#E6EDF3',
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
            {cfg ? 'Sign in to continue.' : 'No authentication configured.'}
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
    );
  }

  // -----------------------------------------------------------------------
  // Version router — session is guaranteed at this point
  // -----------------------------------------------------------------------

  const useV6 =
    typeof window !== 'undefined' &&
    (new URLSearchParams(window.location.search).get('v6') === '1' ||
      new URLSearchParams(window.location.search).get('ui') === 'v6');
  const useV5 =
    typeof window !== 'undefined' &&
    (new URLSearchParams(window.location.search).get('v5') === '1' ||
      new URLSearchParams(window.location.search).get('ui') === 'v5');
  const useV4 =
    typeof window !== 'undefined' &&
    (new URLSearchParams(window.location.search).get('v4') === '1' ||
      new URLSearchParams(window.location.search).get('ui') === 'v4');
  const useV3 =
    typeof window !== 'undefined' &&
    (new URLSearchParams(window.location.search).get('v3') === '1' ||
      new URLSearchParams(window.location.search).get('ui') === 'v3');
  const useV2 =
    typeof window !== 'undefined' &&
    (new URLSearchParams(window.location.search).get('v2') === '1' ||
      new URLSearchParams(window.location.search).get('ui') === 'v2');
  const useV1 =
    typeof window !== 'undefined' &&
    (new URLSearchParams(window.location.search).get('v1') === '1' ||
      new URLSearchParams(window.location.search).get('ui') === 'v1');

  return (
    <QueryClientProvider client={qc}>
      {useV6 ? (
        <V6App onAuthExpired={handleAuthExpired} />
      ) : useV5 ? (
        <V5App onAuthExpired={handleAuthExpired} />
      ) : useV4 ? (
        <V4App onAuthExpired={handleAuthExpired} />
      ) : useV3 ? (
        <V3App onAuthExpired={handleAuthExpired} />
      ) : useV2 ? (
        <V2App onAuthExpired={handleAuthExpired} />
      ) : useV1 ? (
        <V1App onAuthExpired={handleAuthExpired} />
      ) : (
        <V6App onAuthExpired={handleAuthExpired} />
      )}
    </QueryClientProvider>
  );
}
