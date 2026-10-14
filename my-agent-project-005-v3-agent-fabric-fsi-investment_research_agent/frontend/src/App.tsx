import { AuthProvider, useAuthContext } from 'react-oauth2-code-pkce';
import { authConfig, extractInstanceUrl, fetchUserInfo } from './services/authService';
import { useAgentStore } from './store/agentStore';
import Layout from './components/Layout';
import LoginButton from './components/LoginButton';
import { useEffect, createContext, useContext } from 'react';

// Re-export auth context for child components
interface AuthCtx {
  token: string;
  logIn: () => void;
  logOut: () => void;
}
const AuthBridgeContext = createContext<AuthCtx | null>(null);
export const useAuth = () => useContext(AuthBridgeContext);

function AuthenticatedApp() {
  const { token, tokenData, logIn, logOut } = useAuthContext();
  const { accessToken, setAuth } = useAgentStore();

  // Sync OAuth token into Zustand store
  useEffect(() => {
    if (token && !accessToken) {
      const instanceUrl = extractInstanceUrl(
        (tokenData as Record<string, unknown>) ?? {},
      );
      fetchUserInfo(token, instanceUrl)
        .then((user) => setAuth(token, instanceUrl, user))
        .catch(() =>
          setAuth(token, instanceUrl, {
            name: 'Analyst',
            email: '',
            userId: '',
          }),
        );
    }
  }, [token, accessToken, tokenData, setAuth]);

  if (!token) {
    return <LoginButton onLogin={logIn} />;
  }

  return (
    <AuthBridgeContext.Provider value={{ token, logIn, logOut }}>
      <Layout />
    </AuthBridgeContext.Provider>
  );
}

export default function App() {
  return (
    <AuthProvider authConfig={authConfig}>
      <AuthenticatedApp />
    </AuthProvider>
  );
}
