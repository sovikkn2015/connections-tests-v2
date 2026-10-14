import { useState, useCallback, useEffect } from "react";
import type { AuditEntry, AuditFilters } from "@/api/types";
import { mockAuditTrail } from "@/mock/mockData";
import * as gateway from "@/api/gateway";

const DEV_MODE = import.meta.env.DEV;

export function useAuditTrail() {
  const [entries, setEntries] = useState<AuditEntry[]>(DEV_MODE ? mockAuditTrail : []);
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);
  const [filters, setFilters] = useState<AuditFilters>({});
  const [loading, setLoading] = useState(false);

  const fetchEntries = useCallback(async (f: AuditFilters) => {
    if (DEV_MODE) return;
    setLoading(true);
    try { setEntries(await gateway.getAuditTrail(f)); } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (!DEV_MODE) void fetchEntries(filters); }, [filters, fetchEntries]);

  return {
    entries, selectedEntry, filters, loading,
    selectEntry: useCallback((e: AuditEntry) => setSelectedEntry(e), []),
    closeDetail: useCallback(() => setSelectedEntry(null), []),
    updateFilters: useCallback((f: AuditFilters) => setFilters(f), []),
  };
}
