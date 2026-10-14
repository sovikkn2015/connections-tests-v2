import { AlertTriangle, Shield, TrendingUp } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Badge } from "@/components/shared/Badge";

const mockAlerts = [
  { id: "alert-1", type: "bsa_aml" as const, title: "BSA/AML: Unusual transaction pattern", client: "James Henderson", detail: "3 wire transfers >$10K in 48 hours", severity: "warning" as const, timestamp: "2026-04-18T09:30:00Z" },
  { id: "alert-2", type: "concentration" as const, title: "Concentration Warning", client: "Maria Martinez", detail: "TSLA position at 42% — exceeds 40% limit", severity: "danger" as const, timestamp: "2026-04-18T08:15:00Z" },
  { id: "alert-3", type: "review_due" as const, title: "Annual Review Overdue", client: "David Anderson", detail: "Last review: 13 months ago (limit: 12)", severity: "warning" as const, timestamp: "2026-04-17T16:00:00Z" },
];

const iconMap = { bsa_aml: Shield, concentration: TrendingUp, review_due: AlertTriangle };

export function ComplianceAlerts() {
  return (
    <div className="space-y-3">
      {mockAlerts.map((alert) => {
        const Icon = iconMap[alert.type];
        return (
          <Card key={alert.id} variant="interactive">
            <div className="flex items-start gap-3">
              <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${alert.severity === "danger" ? "text-red-600 dark:text-red-400" : "text-yellow-600 dark:text-yellow-400"}`} aria-hidden="true" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium">{alert.title}</span>
                  <Badge variant={alert.severity === "danger" ? "danger" : "warning"}>{alert.severity}</Badge>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400">{alert.client} — {alert.detail}</p>
                <p className="text-xs text-gray-400 mt-1">{new Date(alert.timestamp).toLocaleString()}</p>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
