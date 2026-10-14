import { StatusDot } from "@/components/shared/StatusDot";
import { Badge } from "@/components/shared/Badge";
import { DataTable, type Column } from "@/components/shared/DataTable";
import type { AdapterHealth, CircuitBreakerState } from "@/api/types";

interface Props { adapters: AdapterHealth[]; }

const cbVariant: Record<CircuitBreakerState, "success" | "danger" | "warning"> = { CLOSED: "success", OPEN: "danger", HALF_OPEN: "warning" };

const columns: Column<AdapterHealth>[] = [
  { key: "name", header: "Adapter", render: (r) => <span className="font-medium">{r.name}</span>, sortable: true },
  { key: "vendor", header: "Vendor", render: (r) => r.vendor },
  { key: "protocol", header: "Protocol", render: (r) => <span className="font-mono text-xs">{r.protocol}</span> },
  { key: "status", header: "Status", render: (r) => <StatusDot status={r.status} label={r.status.toUpperCase()} /> },
  { key: "cb", header: "CB", render: (r) => <Badge variant={cbVariant[r.circuitBreaker]}>{r.circuitBreaker}</Badge> },
  { key: "last", header: "Last OK", render: (r) => <span className="text-xs text-gray-500">{r.lastSuccess}</span> },
];

export function AdapterStatus({ adapters }: Props) {
  return <DataTable columns={columns} data={adapters} keyExtractor={(r) => r.name} emptyMessage="No adapters configured" />;
}
