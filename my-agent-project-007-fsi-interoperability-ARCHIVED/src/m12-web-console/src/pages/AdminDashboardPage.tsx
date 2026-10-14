import { SystemHealth } from "@/components/admin/SystemHealth";
import { AdapterStatus } from "@/components/admin/AdapterStatus";
import { PerformanceMetrics } from "@/components/admin/PerformanceMetrics";
import { useSystemHealth } from "@/hooks/useSystemHealth";

export function AdminDashboardPage() {
  const { layers, adapters, metrics } = useSystemHealth();
  return (
    <div className="p-4 space-y-6">
      <h1 className="text-xl font-semibold">System Health</h1>
      <SystemHealth layers={layers} />
      <div><h2 className="text-lg font-semibold mb-3">Adapter Status</h2><AdapterStatus adapters={adapters} /></div>
      <div><h2 className="text-lg font-semibold mb-3">Performance (last 1 hour)</h2><PerformanceMetrics metrics={metrics} /></div>
    </div>
  );
}
