/**
 * AuthCallback — PKCE code exchange landing page for Cognito.
 *
 * Cognito's hosted UI redirects back to `/auth/callback?code=xxxxx` after
 * the user authenticates. This component exchanges that code for tokens,
 * writes the session to localStorage + the session store, then redirects
 * back to the original URL the user was trying to load (or `/` if none).
 *
 * All three outcomes handled honestly:
 *   - ?code=... AND state valid  -> exchange + redirect home
 *   - ?error=access_denied       -> show error, offer retry
 *   - no code at all             -> redirect to /?reason=no_code
 */

import { useEffect, useState } from 'react';
import { exchangeCode } from './cognito';
import { useSessionStore } from '../../shared/store/session';

const RETURN_TO_KEY = 'v3.cognito.return_to';

export function AuthCallback() {
  const [status, setStatus] = useState<'pending' | 'error'>('pending');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const err = params.get('error');
    const errDesc = params.get('error_description');

    if (err) {
      setStatus('error');
      setErrorMsg(errDesc || err);
      return;
    }
    if (!code) {
      // No code and no error — probably a manual visit to the callback URL.
      window.location.replace('/?reason=no_code');
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const session = await exchangeCode(code);
        if (cancelled) return;

        // Hand the Cognito identity to the session store so all API calls
        // use the real access token. correlation_id gets a fresh UUID per
        // browser session; the agent-proxy will stamp turns with their own.
        useSessionStore.getState().setAuth({
          sessionToken: session.accessToken,
          principalId: session.principalId,
          principalName: session.principalName,
          sessionId: crypto.randomUUID(),
          correlationId: crypto.randomUUID(),
        });

        // Navigate back to where the user started. Defaults to root so
        // the v3 persona router takes over.
        const ret =
          window.localStorage.getItem(RETURN_TO_KEY) || '/?persona=research&v3=1';
        window.localStorage.removeItem(RETURN_TO_KEY);
        window.location.replace(ret);
      } catch (exc) {
        if (!cancelled) {
          setStatus('error');
          setErrorMsg((exc as Error).message);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (status === 'pending') {
    return (
      <div
        role="status"
        aria-live="polite"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--forensic-bg-2, #0B1B2F)',
          color: 'var(--forensic-text-1, #E6EDF3)',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
            Completing sign-in…
          </div>
          <div style={{ fontSize: 13, opacity: 0.75 }}>
            Exchanging authorization code with Cognito
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      role="alert"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--forensic-bg-2, #0B1B2F)',
        color: 'var(--forensic-text-1, #E6EDF3)',
        fontFamily: 'Inter, system-ui, sans-serif',
      }}
    >
      <div style={{ maxWidth: 480, padding: '2rem' }}>
        <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 12 }}>
          Sign-in failed
        </div>
        <div style={{ fontSize: 13, marginBottom: 20, opacity: 0.8 }}>
          {errorMsg ?? 'Cognito returned an error during the PKCE code exchange.'}
        </div>
        <button
          type="button"
          onClick={() => window.location.replace('/?persona=research&v3=1')}
          style={{
            padding: '0.5rem 1rem',
            background: 'var(--w360-brand-500, #1B96FF)',
            color: '#FFFFFF',
            border: 0,
            borderRadius: 4,
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}
