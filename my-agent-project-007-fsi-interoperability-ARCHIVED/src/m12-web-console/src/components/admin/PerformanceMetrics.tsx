import { DataTable, type Column } from "@/components/shared/DataTable";
import type { PerformanceMetric } from "@/api/types";

interface Props { metrics: PerformanceMetric[]; }

const columns: Column<PerformanceMetric>[] = [
  { key: "service", header: "Service", render: (r) => <span className="font-medium">{r.service}</span> },
  { key: "p50", header: "p50", render: (r) => <span className="font-mono text-xs">{r.p50}ms</span>, className: "text-right" },
  { key: "p95", header: "p95", render: (r) => <span className="font-mono text-xs">{r.p95}ms</span>, className: "text-right" },
  { key: "p99", header: "p99", render: (r) => <span className="font-mono text-xs">{r.p99}ms</span>, className: "text-right" },
  { key: "throughput", header: "Throughput", render: (r) => <span className="text-xs">{r.throughput}</span>, className: "text-right" },
];

export function PerformanceMetrics({ metrics }: Props) {
  return <DataTable columns={columns} data={metrics} keyExtractor={(r) => r.service} emptyMessage="No metrics available" />;
}
