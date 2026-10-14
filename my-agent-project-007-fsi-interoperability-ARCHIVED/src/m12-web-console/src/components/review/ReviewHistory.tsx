import { Badge } from "@/components/shared/Badge";
import { DataTable, type Column } from "@/components/shared/DataTable";
import type { ReviewItem } from "@/api/types";

interface Props { items: ReviewItem[]; }

const columns: Column<ReviewItem>[] = [
  { key: "advisor", header: "Advisor", render: (r) => r.advisorName, sortable: true },
  { key: "client", header: "Client", render: (r) => r.clientName, sortable: true },
  { key: "type", header: "Type", render: (r) => r.type },
  { key: "status", header: "Status", render: (r) => <Badge variant={r.status === "approved" ? "success" : r.status === "rejected" ? "danger" : "warning"}>{r.status}</Badge> },
  { key: "submitted", header: "Submitted", render: (r) => new Date(r.submittedAt).toLocaleString(), sortable: true },
];

export function ReviewHistory({ items }: Props) {
  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-4">Completed Reviews</h2>
      <DataTable columns={columns} data={items} keyExtractor={(r) => r.id} emptyMessage="No completed reviews" />
    </div>
  );
}
