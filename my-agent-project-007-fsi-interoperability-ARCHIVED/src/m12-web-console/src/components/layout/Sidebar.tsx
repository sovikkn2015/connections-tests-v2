import { NavLink } from "react-router-dom";
import {
  MessageSquare, Users, ShoppingCart, ClipboardList, History,
  FileSearch, Shield, AlertTriangle, Activity, Cpu, FileCode, BarChart3,
} from "lucide-react";
import { useAuth } from "@/auth/useAuth";
import { useAppStore } from "@/store/useAppStore";
import type { UserRole } from "@/api/types";

interface NavItem {
  to: string;
  label: string;
  icon: typeof MessageSquare;
  roles: UserRole[];
  section: string;
}

const navItems: NavItem[] = [
  { to: "/", label: "Chat", icon: MessageSquare, roles: ["advisor", "principal", "admin"], section: "Workspace" },
  { to: "/clients", label: "Clients", icon: Users, roles: ["advisor", "principal", "admin"], section: "Workspace" },
  { to: "/orders", label: "Orders", icon: ShoppingCart, roles: ["advisor", "principal", "admin"], section: "Workspace" },
  { to: "/reviews", label: "Pending", icon: ClipboardList, roles: ["principal", "admin"], section: "Reviews" },
  { to: "/reviews/history", label: "History", icon: History, roles: ["principal", "admin"], section: "Reviews" },
  { to: "/audit", label: "Audit Trail", icon: FileSearch, roles: ["compliance_officer", "admin"], section: "Compliance" },
  { to: "/opa-log", label: "OPA Log", icon: Shield, roles: ["compliance_officer", "admin"], section: "Compliance" },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle, roles: ["compliance_officer", "admin"], section: "Compliance" },
  { to: "/admin", label: "Health", icon: Activity, roles: ["admin"], section: "Admin" },
  { to: "/admin/adapters", label: "Adapters", icon: Cpu, roles: ["admin"], section: "Admin" },
  { to: "/admin/opa", label: "OPA Status", icon: FileCode, roles: ["admin"], section: "Admin" },
  { to: "/admin/metrics", label: "Metrics", icon: BarChart3, roles: ["admin"], section: "Admin" },
];

export function Sidebar() {
  const { user } = useAuth();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const role = user?.role ?? "advisor";

  const visible = navItems.filter((item) => item.roles.includes(role));
  const sections = [...new Set(visible.map((i) => i.section))];

  return (
    <aside
      className={`hidden md:flex flex-col bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 transition-all duration-200 ${collapsed ? "w-16" : "w-56"}`}
      aria-label="Main navigation"
    >
      <nav className="flex-1 py-4 overflow-y-auto">
        {sections.map((section) => (
          <div key={section} className="mb-4">
            {!collapsed && (
              <p className="px-4 mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                {section}
              </p>
            )}
            {visible
              .filter((i) => i.section === section)
              .map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
                      isActive
                        ? "text-blue-800 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/20 font-medium"
                        : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
                    }`
                  }
                >
                  <item.icon className="w-4 h-4 shrink-0" aria-hidden="true" />
                  {!collapsed && <span>{item.label}</span>}
                </NavLink>
              ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
