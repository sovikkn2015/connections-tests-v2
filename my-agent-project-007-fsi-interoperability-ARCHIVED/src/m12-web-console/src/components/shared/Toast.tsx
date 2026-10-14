import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";
import { useAppStore, type Notification } from "@/store/useAppStore";

const iconMap = { success: CheckCircle, error: XCircle, warning: AlertTriangle, info: Info };
const colorMap = {
  success: "border-green-500 bg-green-50 dark:bg-green-950/30",
  error: "border-red-500 bg-red-50 dark:bg-red-950/30",
  warning: "border-yellow-500 bg-yellow-50 dark:bg-yellow-950/30",
  info: "border-blue-500 bg-blue-50 dark:bg-blue-950/30",
};

function ToastItem({ notification }: { notification: Notification }) {
  const dismiss = useAppStore((s) => s.dismissNotification);
  const Icon = iconMap[notification.type];
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border-l-4 ${colorMap[notification.type]} shadow-md`} role="alert">
      <Icon className="w-5 h-5 mt-0.5 shrink-0" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{notification.title}</p>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">{notification.message}</p>
      </div>
      <button onClick={() => dismiss(notification.id)} className="p-0.5 rounded hover:bg-black/5" aria-label="Dismiss notification">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const notifications = useAppStore((s) => s.notifications);
  if (notifications.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full" aria-live="polite">
      {notifications.slice(0, 5).map((n) => <ToastItem key={n.id} notification={n} />)}
    </div>
  );
}
