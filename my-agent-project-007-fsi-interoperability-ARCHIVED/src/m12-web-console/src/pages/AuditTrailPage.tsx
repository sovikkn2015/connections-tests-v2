import { AuditTrailViewer } from "@/components/compliance/AuditTrailViewer";
import { AuditDetailDrawer } from "@/components/compliance/AuditDetailDrawer";
import { useAuditTrail } from "@/hooks/useAuditTrail";

export function AuditTrailPage() {
  const { entries, selectedEntry, selectEntry, closeDetail } = useAuditTrail();
  return (
    <div className="p-4 h-full">
      <h1 className="text-xl font-semibold mb-4">Audit Trail</h1>
      <AuditTrailViewer entries={entries} onSelect={selectEntry} selectedId={selectedEntry?.id} />
      <AuditDetailDrawer entry={selectedEntry} onClose={closeDetail} />
    </div>
  );
}
