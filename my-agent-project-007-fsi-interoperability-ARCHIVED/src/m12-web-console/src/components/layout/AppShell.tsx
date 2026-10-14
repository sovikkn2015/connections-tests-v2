import { Outlet, useNavigate } from "react-router-dom";
import { MessageSquare, Users, ClipboardList, Settings } from "lucide-react";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { ToastContainer } from "@/components/shared/Toast";
import { useAppStore } from "@/store/useAppStore";

const mobileTabs = [
  { key: "chat", label: "Chat", icon: MessageSquare, to: "/" },
  { key: "clients", label: "Clients", icon: Users, to: "/clients" },
  { key: "reviews", label: "Reviews", icon: ClipboardList, to: "/reviews" },
  { key: "settings", label: "Settings", icon: Settings, to: "/settings" },
];

export function AppShell() {
  const { mobileTab, setMobileTab } = useAppStore();
  const navigate = useNavigate();

  return (
    <div className="flex flex-col h-screen">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-950">
          <Outlet />
        </main>
      </div>
      <nav className="md:hidden flex border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900" aria-label="Mobile navigation">
        {mobileTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setMobileTab(tab.key); navigate(tab.to); }}
            className={`flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] transition-colors ${mobileTab === tab.key ? "text-blue-800 dark:text-blue-400" : "text-gray-500 dark:text-gray-400"}`}
            aria-current={mobileTab === tab.key ? "page" : undefined}
          >
            <tab.icon className="w-5 h-5" aria-hidden="true" />
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>
      <ToastContainer />
    </div>
  );
}
