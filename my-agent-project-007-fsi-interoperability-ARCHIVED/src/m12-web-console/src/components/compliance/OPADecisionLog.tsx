import { Badge } from "@/components/shared/Badge";
import { Card } from "@/components/shared/Card";
import type { AuditEntry, AuditDecision } from "@/api/types";

interface Props { entries: AuditEntry[]; }

const decisionVariant: Record<AuditDecision, "success" | "danger" | "warning"> = {
  ALLOW: "success", DENY: "danger", ESCALATE: "warning", BLOCK: "danger",
};

export function OPADecisionLog({ entries }: Props) {
  return (
    <div className="space-y-3">
      {entries.length === 0 && <p className="text-sm text-gray-500 text-center py-8">No OPA decisions to display</p>}
      {entries.map((entry) => (
        <Card key={entry.id} variant="interactive">
          <div className="flex items-center justify-between mb-1">
            <span className="font-mono text-xs text-gray-500">{entry.traceId}</span>
            <Badge variant={decisionVariant[entry.decision]}>{entry.decision}</Badge>
          </div>
          <p className="text-sm"><span className="font-medium">{entry.actor}</span> → <span className="font-mono text-xs">{entry.action}</span> → {entry.target}</p>
          <p className="text-xs text-gray-500 mt-1">{new Date(entry.timestamp).toLocaleString()}</p>
        </Card>
      ))}
    </div>
  );
}
