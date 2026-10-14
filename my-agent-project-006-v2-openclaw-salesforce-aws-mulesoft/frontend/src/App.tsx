/**
 * Root component — SF OAuth2 PKCE for user identity + OpenClaw WebSocket connection.
 * SF OAuth is used ONLY for user identity. Agent communication goes through OpenClaw.
 */

import { AuthProvider, useAuthContext } from 'react-oauth2-code-pkce';
import { authConfig, extractInstanceUrl, fetchUserInfo } from './services/authService';
import { setOAuthToken, setAuthToken } from './services/openclawApi';
import { useAgentStore } from './store/agentStore';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import LoginButton from './components/LoginButton';
import { useEffect } from 'react';

function AuthenticatedApp() {
  const { token, tokenData, logIn, logOut } = useAuthContext();
  const { sfToken, setAuth, setAuthCallbacks, connectToOpenClaw } = useAgentStore();

  useEffect(() => {
    setAuthCallbacks(logIn, logOut);
  }, [logIn, logOut, setAuthCallbacks]);

  useEffect(() => {
    if (token && !sfToken) {
      const instanceUrl = extractInstanceUrl(
        (tokenData as Record<string, unknown>) ?? {},
      );
      fetchUserInfo(token, instanceUrl)
        .then((user) => {
          setAuth(token, instanceUrl, user);
          // Provide OAuth token for AgentCore WebSocket auth (Sec-WebSocket-Protocol)
          setAuthToken(token);
          setOAuthToken(token);
          connectToOpenClaw();
        })
        .catch(() => {
          setAuth(token, instanceUrl, { name: 'Analyst', email: '', userId: '' });
          setAuthToken(token);
          setOAuthToken(token);
          connectToOpenClaw();
        });
    }
  }, [token, sfToken, tokenData, setAuth, connectToOpenClaw]);

  if (!token) {
    return <LoginButton onLogin={logIn} />;
  }

  return (
    <ErrorBoundary>
      <Layout />
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <AuthProvider authConfig={authConfig}>
      <AuthenticatedApp />
    </AuthProvider>
  );
}
