import { SLABadge } from "./SLABadge";
import type { ReviewItem } from "@/api/types";

interface Props { items: ReviewItem[]; selectedId: string | null; onSelect: (item: ReviewItem) => void; }

export function ReviewQueue({ items, selectedId, onSelect }: Props) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-sm font-semibold">Pending Reviews ({items.length})</h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {items.map((item) => (
          <button key={item.id} onClick={() => onSelect(item)}
            className={`w-full text-left px-3 py-3 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${selectedId === item.id ? "bg-blue-50 dark:bg-blue-950/20 border-l-2 border-l-blue-600" : ""}`}>
            <div className="flex items-center justify-between mb-1">
              <SLABadge deadline={item.slaDeadline} />
              <span className="text-[10px] text-gray-400">{new Date(item.submittedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            </div>
            <p className="text-sm font-medium truncate">{item.advisorName} → {item.clientName}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{item.type}</p>
          </button>
        ))}
      </div>
      <div className="p-2 border-t border-gray-200 dark:border-gray-700 text-[10px] text-gray-400 flex gap-3">
        <span>↑↓ Navigate</span><span>A Approve</span><span>R Reject</span><span>E Edit</span>
      </div>
    </div>
  );
}
