import { Clock } from "lucide-react";

interface Props { deadline: string; }

export function SLABadge({ deadline }: Props) {
  const ms = new Date(deadline).getTime() - Date.now();
  const mins = Math.max(0, Math.floor(ms / 60000));
  const hours = Math.floor(mins / 60);
  const remaining = mins % 60;
  const label = hours > 0 ? `${hours}:${String(remaining).padStart(2, "0")}` : `0:${String(mins).padStart(2, "0")}`;
  const color = mins < 60 ? "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30" :
                mins < 120 ? "text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-950/30" :
                "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30";
  const statusText = mins < 60 ? "Critical" : mins < 120 ? "Warning" : "On track";

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${color}`} role="status" aria-label={`SLA ${statusText}: ${label} remaining`}>
      <Clock className="w-3 h-3" aria-hidden="true" />{label}
    </span>
  );
}
