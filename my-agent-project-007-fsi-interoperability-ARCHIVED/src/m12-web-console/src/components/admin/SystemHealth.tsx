import { Card } from "@/components/shared/Card";
import { StatusDot } from "@/components/shared/StatusDot";
import type { LayerHealth } from "@/api/types";

interface Props { layers: LayerHealth[]; }

export function SystemHealth({ layers }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {layers.map((layer) => {
        const worstStatus = layer.modules.some((m) => m.status === "down") ? "down" as const :
                           layer.modules.some((m) => m.status === "degraded") ? "degraded" as const : "healthy" as const;
        return (
          <Card key={layer.name}>
            <div className="flex items-center gap-2 mb-3"><StatusDot status={worstStatus} size="md" /><h3 className="text-sm font-semibold uppercase">{layer.name}</h3></div>
            <div className="space-y-1.5">
              {layer.modules.map((mod) => (
                <div key={mod.module} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2"><StatusDot status={mod.status} /><span>{mod.module}</span></div>
                  <span className="text-xs text-gray-500 font-mono">{mod.latencyMs}ms</span>
                </div>
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
