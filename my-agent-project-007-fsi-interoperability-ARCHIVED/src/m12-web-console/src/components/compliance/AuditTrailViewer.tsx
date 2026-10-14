import { Badge } from "@/components/shared/Badge";
import { DataTable, type Column } from "@/components/shared/DataTable";
import type { AuditEntry, AuditDecision } from "@/api/types";

interface Props { entries: AuditEntry[]; onSelect: (entry: AuditEntry) => void; selectedId?: string; }

const decisionVariant: Record<AuditDecision, "success" | "danger" | "warning"> = {
  ALLOW: "success", DENY: "danger", ESCALATE: "warning", BLOCK: "danger",
};

const columns: Column<AuditEntry>[] = [
  { key: "time", header: "Time", render: (r) => new Date(r.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), sortable: true, className: "w-16" },
  { key: "trace", header: "Trace", render: (r) => <span className="font-mono text-xs">{r.traceId}</span>, className: "w-20" },
  { key: "actor", header: "Actor", render: (r) => r.actor, sortable: true },
  { key: "action", header: "Action", render: (r) => <span className="font-mono text-xs">{r.action}</span> },
  { key: "target", header: "Target", render: (r) => r.target },
  { key: "decision", header: "Decision", render: (r) => <Badge variant={decisionVariant[r.decision]}>{r.decision}</Badge> },
  { key: "module", header: "Module", render: (r) => r.module, className: "w-14" },
];

export function AuditTrailViewer({ entries, onSelect, selectedId }: Props) {
  return <DataTable columns={columns} data={entries} keyExtractor={(r) => r.id} onRowClick={onSelect} selectedKey={selectedId} emptyMessage="No audit entries match your filters" />;
}
