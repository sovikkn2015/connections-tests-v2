import { CheckCircle, RefreshCw } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Badge } from "@/components/shared/Badge";

const mockPolicies = [
  { bundle: "authority", version: "v2.4.1", tests: 142, passing: 142, lastSync: "2m ago" },
  { bundle: "mnpi", version: "v2.4.1", tests: 89, passing: 89, lastSync: "2m ago" },
  { bundle: "compliance", version: "v2.4.1", tests: 47, passing: 47, lastSync: "2m ago" },
];

export function OPAPolicyStatus() {
  return (
    <div className="space-y-3">
      {mockPolicies.map((p) => (
        <Card key={p.bundle}>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">{p.bundle}</h3>
              <p className="text-xs text-gray-500 mt-0.5">Version: <span className="font-mono">{p.version}</span> · Last sync: {p.lastSync}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={p.passing === p.tests ? "success" : "warning"}><CheckCircle className="w-3 h-3" aria-hidden="true" />{p.passing}/{p.tests} tests</Badge>
              <button className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800" aria-label={`Sync ${p.bundle} bundle`}><RefreshCw className="w-4 h-4 text-gray-400" /></button>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
