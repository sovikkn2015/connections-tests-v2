/**
 * Cognito auth — OAuth 2.0 PKCE flow for the v3 frontend.
 *
 * Replaces v2's `dev-bootstrap-token` bootstrap with real Cognito hosted UI
 * authentication. When `VITE_COGNITO_DOMAIN` + `VITE_COGNITO_CLIENT_ID` are
 * present, the SPA:
 *
 *   1. On first load, checks for existing session in localStorage.
 *   2. If no session, redirects browser to Cognito hosted UI with PKCE challenge.
 *   3. On `/v3/auth/callback`, exchanges code for tokens via PKCE verifier.
 *   4. Stores the access token + id token + refresh token in localStorage.
 *   5. Hands the access token to the session store for API calls.
 *
 * Falls back gracefully: if Cognito env vars are absent, or if
 * `VITE_AUTH_DEV_BOOTSTRAP=1` is set, the SPA mints the old dev-bootstrap
 * token instead — demos still work.
 *
 * Token refresh: access tokens from Cognito are 1hr by default. We refresh
 * at 55min using the refresh token. Any 401 from the API triggers an
 * immediate refresh + retry once before bouncing to the IdP.
 *
 * No credentials are kept in code. All Cognito identifiers come from Vite
 * env injection at build time.
 */

const STORAGE_KEY = 'v3.cognito.session';
const PKCE_VERIFIER_KEY = 'v3.cognito.pkce.verifier';

export interface CognitoConfig {
  domain: string; // e.g. https://openclaw-v3.auth.us-east-1.amazoncognito.com
  clientId: string;
  redirectUri: string; // e.g. https://d2zs9nk4uc2dbx.cloudfront.net/auth/callback
  scope?: string; // default: "openid profile email"
}

export interface CognitoSession {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresAt: number; // epoch ms
  principalId: string;
  principalName: string;
  email?: string;
}

export interface CognitoJwtClaims {
  sub: string;
  email?: string;
  name?: string;
  'cognito:username'?: string;
  'custom:salesforce_user_id'?: string;
  exp: number;
  iat: number;
  aud?: string;
  iss?: string;
}

export function readConfigFromEnv(): CognitoConfig | null {
  const domain = (import.meta.env.VITE_COGNITO_DOMAIN ?? '') as string;
  const clientId = (import.meta.env.VITE_COGNITO_CLIENT_ID ?? '') as string;
  const redirectUri =
    (import.meta.env.VITE_COGNITO_REDIRECT_URI ?? '') as string ||
    (typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '');
  const scope =
    (import.meta.env.VITE_COGNITO_SCOPE ?? 'openid profile email') as string;

  if (!domain || !clientId || !redirectUri) {
    return null;
  }
  return { domain, clientId, redirectUri, scope };
}

/**
 * True when Cognito is configured AND dev bootstrap is NOT explicitly
 * requested. If both are absent the caller falls back to dev bootstrap.
 */
export function shouldUseCognito(): boolean {
  const cfg = readConfigFromEnv();
  const devBootstrap =
    String(import.meta.env.VITE_AUTH_DEV_BOOTSTRAP ?? '').toLowerCase() === '1';
  return cfg !== null && !devBootstrap;
}

/** Load saved Cognito session from localStorage (returns null on miss or expiry). */
export function loadSession(): CognitoSession | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as CognitoSession;
    // Treat a session as expired 30s before the actual expiry so we refresh
    // before the next request hits a 401.
    if (s.expiresAt - Date.now() < 30_000) {
      return null;
    }
    return s;
  } catch {
    return null;
  }
}

export function saveSession(session: CognitoSession): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    /* quota exceeded or private mode — ignore */
  }
}

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.removeItem(PKCE_VERIFIER_KEY);
  } catch {
    /* ignore */
  }
}

/** Start the PKCE login flow by redirecting to Cognito hosted UI. */
export async function startLogin(): Promise<void> {
  const cfg = readConfigFromEnv();
  if (!cfg) throw new Error('Cognito not configured');

  const verifier = randomVerifier();
  window.localStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  const challenge = await pkceChallenge(verifier);

  const url = new URL(`${cfg.domain.replace(/\/$/, '')}/oauth2/authorize`);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('client_id', cfg.clientId);
  url.searchParams.set('redirect_uri', cfg.redirectUri);
  url.searchParams.set('scope', cfg.scope ?? 'openid profile email');
  url.searchParams.set('code_challenge', challenge);
  url.searchParams.set('code_challenge_method', 'S256');
  window.location.assign(url.toString());
}

/**
 * Exchange the authorization code on `/auth/callback` for tokens. Called by
 * the callback route. Returns the resulting session on success; throws on
 * failure so the caller can show an error screen.
 */
export async function exchangeCode(code: string): Promise<CognitoSession> {
  const cfg = readConfigFromEnv();
  if (!cfg) throw new Error('Cognito not configured');
  const verifier = window.localStorage.getItem(PKCE_VERIFIER_KEY);
  if (!verifier) throw new Error('PKCE verifier missing — cannot complete auth');

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: cfg.clientId,
    code,
    redirect_uri: cfg.redirectUri,
    code_verifier: verifier,
  });

  const resp = await fetch(`${cfg.domain.replace(/\/$/, '')}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!resp.ok) {
    const errText = await resp.text().catch(() => '');
    throw new Error(`Cognito token exchange ${resp.status}: ${errText.slice(0, 200)}`);
  }

  const data = (await resp.json()) as {
    access_token: string;
    id_token: string;
    refresh_token: string;
    expires_in: number;
    token_type: string;
  };

  const claims = decodeJwtPayload(data.id_token);
  const session: CognitoSession = {
    accessToken: data.access_token,
    idToken: data.id_token,
    refreshToken: data.refresh_token,
    expiresAt: Date.now() + data.expires_in * 1000,
    principalId: claims.sub,
    principalName:
      claims.name ?? claims['cognito:username'] ?? claims.email ?? 'User',
    email: claims.email,
  };
  saveSession(session);
  window.localStorage.removeItem(PKCE_VERIFIER_KEY);
  return session;
}

/**
 * Refresh the access token using the stored refresh token. Returns a new
 * session with updated tokens + expiry. Throws if the refresh token is
 * invalid — caller should clear session and redirect to login.
 */
export async function refresh(session: CognitoSession): Promise<CognitoSession> {
  const cfg = readConfigFromEnv();
  if (!cfg) throw new Error('Cognito not configured');

  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: cfg.clientId,
    refresh_token: session.refreshToken,
  });

  const resp = await fetch(`${cfg.domain.replace(/\/$/, '')}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!resp.ok) {
    clearSession();
    throw new Error(`Cognito refresh failed ${resp.status}`);
  }
  const data = (await resp.json()) as {
    access_token: string;
    id_token: string;
    expires_in: number;
  };
  const refreshed: CognitoSession = {
    ...session,
    accessToken: data.access_token,
    idToken: data.id_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  saveSession(refreshed);
  return refreshed;
}

/**
 * Minimal JWT payload decoder — no signature verification (that happens
 * server-side on the agent-proxy Lambda). We only decode here to read the
 * user identity claims. Cognito signs with RS256 against a JWKS endpoint
 * the backend fetches; the browser trusts TLS to Cognito's host.
 */
export function decodeJwtPayload(token: string): CognitoJwtClaims {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Invalid JWT shape');
  try {
    const base64 = parts[1]!.replace(/-/g, '+').replace(/_/g, '/');
    const pad = base64.length % 4 ? 4 - (base64.length % 4) : 0;
    const padded = base64 + '='.repeat(pad);
    return JSON.parse(atob(padded)) as CognitoJwtClaims;
  } catch (exc) {
    throw new Error(`JWT payload decode failed: ${(exc as Error).message}`);
  }
}

// ---------------------------------------------------------------------------
// PKCE helpers
// ---------------------------------------------------------------------------

function randomVerifier(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

async function pkceChallenge(verifier: string): Promise<string> {
  const enc = new TextEncoder();
  const digest = await crypto.subtle.digest('SHA-256', enc.encode(verifier));
  return base64UrlEncode(new Uint8Array(digest));
}

function base64UrlEncode(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]!);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
