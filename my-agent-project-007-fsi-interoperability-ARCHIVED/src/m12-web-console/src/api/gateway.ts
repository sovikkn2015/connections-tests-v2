/* ── M6 Gateway HTTP Client ──
   ALL API calls go through this module.
   Authorization header carries the AID token (in-memory, never localStorage).
*/

import type {
  SendMessageRequest,
  ChatMessage,
  ReviewItem,
  ReviewAction,
  AuditEntry,
  AuditFilters,
  LayerHealth,
  AdapterHealth,
  PerformanceMetric,
} from "./types";

let aidToken: string | null = null;

export function setAidToken(token: string | null) {
  aidToken = token;
}

export function getAidToken(): string | null {
  return aidToken;
}

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (aidToken) {
    headers["Authorization"] = `Bearer ${aidToken}`;
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent("auth:expired"));
    throw new Error("Token expired");
  }
  if (res.status === 403) {
    throw new Error("Access denied");
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Gateway error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/* ── Chat ── */

export async function sendMessage(req: SendMessageRequest): Promise<ChatMessage> {
  return request<ChatMessage>("/chat/send", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getChatHistory(conversationId: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/chat/history/${conversationId}`);
}

/* ── Reviews ── */

export async function getReviewQueue(): Promise<ReviewItem[]> {
  return request<ReviewItem[]>("/reviews/pending");
}

export async function getReviewHistory(): Promise<ReviewItem[]> {
  return request<ReviewItem[]>("/reviews/history");
}

export async function submitReviewAction(action: ReviewAction): Promise<{ ok: boolean }> {
  return request("/reviews/action", {
    method: "POST",
    body: JSON.stringify(action),
  });
}

/* ── Audit ── */

export async function getAuditTrail(filters: AuditFilters): Promise<AuditEntry[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, String(v));
  });
  return request<AuditEntry[]>(`/audit/trail?${params.toString()}`);
}

export async function getAuditDetail(traceId: string): Promise<AuditEntry> {
  return request<AuditEntry>(`/audit/detail/${traceId}`);
}

/* ── System Health ── */

export async function getSystemHealth(): Promise<LayerHealth[]> {
  return request<LayerHealth[]>("/admin/health");
}

export async function getAdapterStatus(): Promise<AdapterHealth[]> {
  return request<AdapterHealth[]>("/admin/adapters");
}

export async function getPerformanceMetrics(): Promise<PerformanceMetric[]> {
  return request<PerformanceMetric[]>("/admin/metrics");
}

/* ── Order Approval ── */

export async function approveOrder(orderId: string): Promise<{ ok: boolean }> {
  return request("/orders/approve", {
    method: "POST",
    body: JSON.stringify({ orderId }),
  });
}

export async function rejectOrder(orderId: string, reason: string): Promise<{ ok: boolean }> {
  return request("/orders/reject", {
    method: "POST",
    body: JSON.stringify({ orderId, reason }),
  });
}
