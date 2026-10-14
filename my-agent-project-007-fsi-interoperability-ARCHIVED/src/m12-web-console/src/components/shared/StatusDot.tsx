import { CheckCircle, AlertTriangle, XCircle, HelpCircle } from "lucide-react";
import type { HealthStatus } from "@/api/types";

interface Props {
  status: HealthStatus;
  label?: string;
  size?: "sm" | "md";
}

const config: Record<HealthStatus, { icon: typeof CheckCircle; color: string; text: string }> = {
  healthy: { icon: CheckCircle, color: "text-green-600 dark:text-green-400", text: "Healthy" },
  degraded: { icon: AlertTriangle, color: "text-yellow-600 dark:text-yellow-400", text: "Degraded" },
  down: { icon: XCircle, color: "text-red-600 dark:text-red-400", text: "Down" },
  unknown: { icon: HelpCircle, color: "text-gray-400 dark:text-gray-500", text: "Unknown" },
};

export function StatusDot({ status, label, size = "sm" }: Props) {
  const { icon: Icon, color, text } = config[status];
  const sizeClass = size === "sm" ? "w-4 h-4" : "w-5 h-5";

  return (
    <span className={`inline-flex items-center gap-1 ${color}`} role="status">
      <Icon className={sizeClass} aria-hidden="true" />
      <span className="sr-only">{label ?? text}</span>
      {label && <span className="text-xs font-medium">{label}</span>}
    </span>
  );
}
