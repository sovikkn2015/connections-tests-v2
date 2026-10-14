import { X, ExternalLink } from "lucide-react";
import { Badge } from "@/components/shared/Badge";
import { ProvenanceChain } from "./ProvenanceChain";
import type { AuditEntry } from "@/api/types";

interface Props { entry: AuditEntry | null; onClose: () => void; }

export function AuditDetailDrawer({ entry, onClose }: Props) {
  if (!entry) return null;
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 shadow-2xl z-40 flex flex-col" role="dialog" aria-label="Audit detail">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold">Trace: <span className="font-mono">{entry.traceId}</span></h2>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800" aria-label="Close drawer"><X className="w-5 h-5" /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {entry.provenanceChain && entry.provenanceChain.length > 0 && (
          <div><h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">Provenance Chain</h3><ProvenanceChain stages={entry.provenanceChain} /></div>
        )}
        {entry.mnpiFilter && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">MNPI Filter</h3>
            <div className="text-sm space-y-1">
              <div className="flex items-center gap-2"><span className="text-gray-500">Stripped:</span><div className="flex gap-1">{entry.mnpiFilter.stripped.map((f) => <Badge key={f} variant="mnpi">{f}</Badge>)}</div></div>
              <p><span className="text-gray-500">Rule:</span> <span className="font-mono text-xs">{entry.mnpiFilter.rule}</span></p>
              <p><span className="text-gray-500">Archetype:</span> {entry.mnpiFilter.archetype}</p>
            </div>
          </div>
        )}
        {entry.wormRecord && (
          <div><h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">WORM Record</h3><p className="font-mono text-xs text-gray-600 dark:text-gray-400 break-all">{entry.wormRecord}</p></div>
        )}
        <div className="flex gap-2">
          <button className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"><ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />View Langfuse</button>
          <button className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"><ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />View WORM</button>
          <button className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"><ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />Export JSON</button>
        </div>
      </div>
    </div>
  );
}
