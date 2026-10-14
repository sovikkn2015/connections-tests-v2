import { Menu, Bell, Settings, Moon, Sun, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { useAppStore } from "@/store/useAppStore";

const archLabels: Record<string, string> = {
  tier3_bd: "Tier 3 BD",
  tier4_ria: "Tier 4 RIA",
  tier2_hybrid: "Tier 2 Hybrid",
  tier5_family_office: "Tier 5 FO",
};

export function TopBar() {
  const { user, logout } = useAuth();
  const { toggleSidebar, darkMode, toggleDarkMode, notifications } = useAppStore();
  const navigate = useNavigate();
  const unread = notifications.length;

  return (
    <header className="flex items-center justify-between h-14 px-4 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
      <div className="flex items-center gap-3">
        <button onClick={toggleSidebar} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 hidden md:block" aria-label="Toggle sidebar">
          <Menu className="w-5 h-5" />
        </button>
        <span className="text-lg font-bold text-blue-800 dark:text-blue-400 tracking-tight">007 Platform</span>
      </div>
      <div className="flex items-center gap-3">
        {user && (
          <span className="hidden sm:inline text-sm text-gray-600 dark:text-gray-400">
            {user.name} · <span className="capitalize">{user.role.replace("_", " ")}</span> · {archLabels[user.firm_archetype] ?? user.firm_archetype}
          </span>
        )}
        <button onClick={() => navigate("/notifications")} className="relative p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800" aria-label={`Notifications${unread > 0 ? `, ${unread} unread` : ""}`}>
          <Bell className="w-5 h-5" />
          {unread > 0 && <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center">{unread > 9 ? "9+" : unread}</span>}
        </button>
        <button onClick={toggleDarkMode} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800" aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}>
          {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>
        <button onClick={() => navigate("/settings")} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800" aria-label="Settings">
          <Settings className="w-5 h-5" />
        </button>
        <button onClick={logout} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800" aria-label="Log out">
          <LogOut className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
}
