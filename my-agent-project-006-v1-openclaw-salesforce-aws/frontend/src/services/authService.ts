/**
 * OAuth2 PKCE flow for Salesforce authentication — user identity only.
 * The frontend connects to OpenClaw via WebSocket, NOT Salesforce Agent API.
 * SF OAuth is used solely to identify the analyst user.
 *
 * CORS fix: Salesforce's /services/oauth2/token doesn't return CORS headers
 * for browser-based SPAs on CloudFront. The token exchange is proxied through
 * a Lambda on API Gateway (VITE_SF_TOKEN_PROXY_URL) which calls Salesforce
 * server-side. The authorize endpoint (browser redirect) works fine directly.
 */

import type { TAuthConfig } from 'react-oauth2-code-pkce';

const SF_LOGIN_URL = import.meta.env.VITE_SF_LOGIN_URL || 'https://login.salesforce.com';
const SF_INSTANCE_URL = import.meta.env.VITE_SF_INSTANCE_URL || '';
const SF_CLIENT_ID = import.meta.env.VITE_SF_CLIENT_ID || '';
const SF_REDIRECT_URI = import.meta.env.VITE_SF_REDIRECT_URI || 'http://localhost:5173/callback';

// Token endpoint: use the Lambda proxy to bypass Salesforce CORS restrictions.
// Falls back to direct Salesforce endpoint for local dev (Vite proxy handles CORS).
const SF_TOKEN_ENDPOINT = import.meta.env.VITE_SF_TOKEN_PROXY_URL
  || `${SF_LOGIN_URL}/services/oauth2/token`;

export const authConfig: TAuthConfig = {
  clientId: SF_CLIENT_ID,
  authorizationEndpoint: `${SF_LOGIN_URL}/services/oauth2/authorize`,
  tokenEndpoint: SF_TOKEN_ENDPOINT,
  redirectUri: SF_REDIRECT_URI,
  scope: 'openid refresh_token',
  autoLogin: false,
  clearURL: true,
  decodeToken: false,
  storage: 'local',
  loginMethod: 'redirect',
  // When the refresh token itself expires, log a warning instead of auto-redirecting.
  // This prevents mid-query page reloads. The user can manually re-login when ready.
  onRefreshTokenExpire: (_event) => {
    console.warn('[auth] Refresh token expired — user must re-login');
    // Don't call event.login() here — that would redirect mid-query.
    // The UI will show "disconnected" and the user can click Sign In when ready.
  },
};

export function extractInstanceUrl(tokenData: Record<string, unknown>): string {
  const instanceUrl = tokenData?.instance_url as string | undefined;
  if (instanceUrl) return instanceUrl;
  const idUrl = tokenData?.id as string | undefined;
  if (idUrl) {
    const url = new URL(idUrl);
    return url.origin;
  }
  return SF_INSTANCE_URL || SF_LOGIN_URL;
}

export async function fetchUserInfo(
  accessToken: string,
  instanceUrl: string,
): Promise<{ name: string; email: string; userId: string }> {
  const res = await fetch(`${instanceUrl}/services/oauth2/userinfo`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch user info: ${res.status}`);
  const data = await res.json();
  return {
    name: data.name ?? data.preferred_username ?? 'Analyst',
    email: data.email ?? '',
    userId: data.user_id ?? data.sub ?? '',
  };
}
