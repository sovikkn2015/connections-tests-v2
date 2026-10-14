import { useAuth } from "@/auth/useAuth";
import { Navigate } from "react-router-dom";
import { Button } from "@/components/shared/Button";

export function LoginPage() {
  const { authenticated, login } = useAuth();
  if (authenticated) return <Navigate to="/" replace />;
  return (
    <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-950">
      <div className="text-center space-y-6">
        <h1 className="text-3xl font-bold text-blue-800 dark:text-blue-400">007 Platform</h1>
        <p className="text-gray-600 dark:text-gray-400">FSI Interoperability Platform</p>
        <Button size="lg" onClick={login}>Sign in with Keycloak</Button>
        <p className="text-xs text-gray-400">Authentication via Keycloak · AID token in memory</p>
      </div>
    </div>
  );
}
