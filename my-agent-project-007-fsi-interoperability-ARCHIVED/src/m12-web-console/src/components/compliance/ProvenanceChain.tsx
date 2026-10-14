import { Hash } from "lucide-react";
import type { ProvenanceStage } from "@/api/types";

interface Props { stages: ProvenanceStage[]; }

export function ProvenanceChain({ stages }: Props) {
  return (
    <div className="space-y-0" role="list" aria-label="Provenance chain">
      {stages.map((stage, i) => (
        <div key={i} className="flex gap-3" role="listitem">
          <div className="flex flex-col items-center">
            <div className="w-3 h-3 rounded-full bg-blue-600 dark:bg-blue-400 border-2 border-white dark:border-gray-900 z-10" />
            {i < stages.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 dark:bg-gray-700" />}
          </div>
          <div className="pb-4 min-w-0">
            <p className="text-sm font-medium">{stage.module} — {stage.label}</p>
            <div className="flex items-center gap-1 mt-0.5">
              <Hash className="w-3 h-3 text-gray-400" aria-hidden="true" />
              <span className="font-mono text-xs text-gray-500 dark:text-gray-400 truncate" title={stage.sha256}>SHA: {stage.sha256}</span>
            </div>
            {stage.rule && <p className="text-xs text-gray-500 mt-0.5">Rule: <span className="font-mono">{stage.rule}</span></p>}
            {stage.wspSection && <p className="text-xs text-gray-500">WSP: {stage.wspSection}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
