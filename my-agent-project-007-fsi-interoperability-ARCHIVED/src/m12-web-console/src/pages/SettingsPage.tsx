import { useAuth } from "@/auth/useAuth";
import { Card } from "@/components/shared/Card";
import { Button } from "@/components/shared/Button";

export function SettingsPage() {
  const { user, logout } = useAuth();
  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Card>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-3">Profile (AID Claims)</h2>
        <div className="text-sm space-y-2">
          <div className="flex gap-2"><span className="text-gray-500 w-28">Name:</span><span>{user?.name}</span></div>
          <div className="flex gap-2"><span className="text-gray-500 w-28">Role:</span><span className="capitalize">{user?.role.replace("_", " ")}</span></div>
          <div className="flex gap-2"><span className="text-gray-500 w-28">Firm ID:</span><span className="font-mono text-xs">{user?.firm_id}</span></div>
          <div className="flex gap-2"><span className="text-gray-500 w-28">Archetype:</span><span>{user?.firm_archetype}</span></div>
          {user?.crd_number && <div className="flex gap-2"><span className="text-gray-500 w-28">CRD#:</span><span>{user.crd_number}</span></div>}
          <div className="flex gap-2"><span className="text-gray-500 w-28">Scopes:</span><span className="font-mono text-xs">{user?.scopes.join(", ")}</span></div>
        </div>
      </Card>
      <Card>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-3">Data Consent</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">Control which data categories the AI agent can access on your behalf.</p>
        {["PII (name, contact)", "Holdings & positions", "Trade history", "Financial plans"].map((cat) => (
          <label key={cat} className="flex items-center gap-3 py-1.5 text-sm">
            <input type="checkbox" defaultChecked className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" /><span>{cat}</span>
          </label>
        ))}
      </Card>
      <Button variant="danger" onClick={logout}>Log Out</Button>
    </div>
  );
}
