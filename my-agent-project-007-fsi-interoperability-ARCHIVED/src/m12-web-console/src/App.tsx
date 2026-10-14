import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/auth/AuthProvider";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { AppShell } from "@/components/layout/AppShell";
import { ChatPage } from "@/pages/ChatPage";
import { ReviewQueuePage } from "@/pages/ReviewQueuePage";
import { OrderApprovalPage } from "@/pages/OrderApprovalPage";
import { AuditTrailPage } from "@/pages/AuditTrailPage";
import { AdminDashboardPage } from "@/pages/AdminDashboardPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { LoginPage } from "@/pages/LoginPage";
import { OPADecisionLog } from "@/components/compliance/OPADecisionLog";
import { ComplianceAlerts } from "@/components/compliance/ComplianceAlerts";
import { OPAPolicyStatus } from "@/components/admin/OPAPolicyStatus";
import { mockAuditTrail } from "@/mock/mockData";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
              <Route index element={<ChatPage />} />
              <Route path="clients" element={<ChatPage />} />
              <Route path="orders" element={<OrderApprovalPage />} />
              <Route path="reviews" element={<ProtectedRoute allowedRoles={["principal", "admin"]}><ReviewQueuePage /></ProtectedRoute>} />
              <Route path="reviews/history" element={<ProtectedRoute allowedRoles={["principal", "admin"]}><ReviewQueuePage /></ProtectedRoute>} />
              <Route path="audit" element={<ProtectedRoute allowedRoles={["compliance_officer", "admin"]}><AuditTrailPage /></ProtectedRoute>} />
              <Route path="opa-log" element={<ProtectedRoute allowedRoles={["compliance_officer", "admin"]}><div className="p-4"><h1 className="text-xl font-semibold mb-4">OPA Decision Log</h1><OPADecisionLog entries={mockAuditTrail} /></div></ProtectedRoute>} />
              <Route path="alerts" element={<ProtectedRoute allowedRoles={["compliance_officer", "admin"]}><div className="p-4"><h1 className="text-xl font-semibold mb-4">Compliance Alerts</h1><ComplianceAlerts /></div></ProtectedRoute>} />
              <Route path="admin" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
              <Route path="admin/adapters" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
              <Route path="admin/opa" element={<ProtectedRoute allowedRoles={["admin"]}><div className="p-4"><h1 className="text-xl font-semibold mb-4">OPA Policy Status</h1><OPAPolicyStatus /></div></ProtectedRoute>} />
              <Route path="admin/metrics" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="notifications" element={<SettingsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
