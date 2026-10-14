/* ── Keycloak JS Adapter Wrapper ──
   AID token stored IN MEMORY only (never localStorage) for XSS protection.
*/

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AIDClaims, UserRole } from "@/api/types";
import { setAidToken } from "@/api/gateway";

export interface AuthState {
  authenticated: boolean;
  loading: boolean;
  user: AIDClaims | null;
  login: () => void;
  logout: () => void;
  aidToken: string | null;
}

export const AuthContext = createContext<AuthState>({
  authenticated: false,
  loading: true,
  user: null,
  login: () => {},
  logout: () => {},
  aidToken: null,
});

/* Dev-mode mock user when Keycloak is not available */
const MOCK_USER: AIDClaims = {
  sub: "mock-aid-001",
  name: "Sarah Chen",
  role: "advisor",
  firm_id: "FIRM-001",
  firm_archetype: "tier4_ria",
  scopes: ["client.read", "portfolio.read", "order.submit", "meeting.prep"],
};

const DEV_MODE = import.meta.env.DEV && !import.meta.env.VITE_KEYCLOAK_URL;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(DEV_MODE);
  const [loading, setLoading] = useState(!DEV_MODE);
  const [user, setUser] = useState<AIDClaims | null>(DEV_MODE ? MOCK_USER : null);
  const [token, setToken] = useState<string | null>(DEV_MODE ? "mock-aid-token" : null);

  useEffect(() => {
    if (DEV_MODE) {
      setAidToken("mock-aid-token");
      return;
    }

    async function initKeycloak() {
      try {
        const Keycloak = (await import("keycloak-js")).default;
        const kc = new Keycloak({
          url: import.meta.env.VITE_KEYCLOAK_URL as string,
          realm: import.meta.env.VITE_KEYCLOAK_REALM as string,
          clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID as string,
        });

        const authed = await kc.init({ onLoad: "login-required", checkLoginIframe: false });

        if (authed && kc.token && kc.tokenParsed) {
          const claims: AIDClaims = {
            sub: (kc.tokenParsed["sub"] as string) ?? "",
            name: (kc.tokenParsed["name"] as string) ?? "",
            role: (kc.tokenParsed["role"] as UserRole) ?? "advisor",
            firm_id: (kc.tokenParsed["firm_id"] as string) ?? "",
            firm_archetype: (kc.tokenParsed["firm_archetype"] as AIDClaims["firm_archetype"]) ?? "tier4_ria",
            crd_number: kc.tokenParsed["crd_number"] as string | undefined,
            scopes: (kc.tokenParsed["scopes"] as string[]) ?? [],
          };
          setUser(claims);
          setToken(kc.token);
          setAidToken(kc.token);
          setAuthenticated(true);

          setInterval(async () => {
            try {
              const refreshed = await kc.updateToken(30);
              if (refreshed && kc.token) {
                setToken(kc.token);
                setAidToken(kc.token);
              }
            } catch {
              setAuthenticated(false);
              kc.login();
            }
          }, 60_000);
        }
      } catch {
        setAuthenticated(false);
      } finally {
        setLoading(false);
      }
    }

    void initKeycloak();
  }, []);

  const login = useCallback(() => {
    if (DEV_MODE) {
      setAuthenticated(true);
      setUser(MOCK_USER);
      setToken("mock-aid-token");
      setAidToken("mock-aid-token");
    }
  }, []);

  const logout = useCallback(() => {
    setAuthenticated(false);
    setUser(null);
    setToken(null);
    setAidToken(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ authenticated, loading, user, login, logout, aidToken: token }),
    [authenticated, loading, user, login, logout, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
