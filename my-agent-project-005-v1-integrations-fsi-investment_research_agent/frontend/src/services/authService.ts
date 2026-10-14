/**
 * OAuth2 PKCE flow for Salesforce authentication.
 *
 * Uses react-oauth2-code-pkce for the heavy lifting.
 * This module provides the PKCE config and token helpers.
 * Tokens are kept in memory only — never persisted to localStorage.
 */

import type { TAuthConfig } from 'react-oauth2-code-pkce';

const SF_LOGIN_URL = import.meta.env.VITE_SF_LOGIN_URL || 'https://login.salesforce.com';
const SF_CLIENT_ID = import.meta.env.VITE_SF_CLIENT_ID || '';
const SF_REDIRECT_URI = import.meta.env.VITE_SF_REDIRECT_URI || 'http://localhost:5173/callback';
const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL || '';

/** PKCE config consumed by <AuthProvider> in App.tsx */
export const authConfig: TAuthConfig = {
  clientId: SF_CLIENT_ID,
  authorizationEndpoint: `${SF_LOGIN_URL}/services/oauth2/authorize`,
  tokenEndpoint: `${API_GATEWAY_URL}/oauth/token`,  // Lambda proxy — avoids CORS on SF token endpoint
  redirectUri: SF_REDIRECT_URI,
  scope: 'api refresh_token',
  autoLogin: false,
  clearURL: true,
  decodeToken: false,
  storage: 'session',
  loginMethod: 'redirect',
};

/** Extract the Salesforce instance URL from the token response */
export function extractInstanceUrl(tokenData: Record<string, unknown>): string {
  const instanceUrl = tokenData?.instance_url as string | undefined;
  if (instanceUrl) return instanceUrl;
  const idUrl = tokenData?.id as string | undefined;
  if (idUrl) {
    const url = new URL(idUrl);
    return url.origin;
  }
  return SF_LOGIN_URL;
}

/** Fetch user info from Salesforce using the access token */
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
