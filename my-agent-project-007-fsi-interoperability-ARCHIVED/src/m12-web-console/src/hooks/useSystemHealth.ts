import { useState, useEffect } from "react";
import type { LayerHealth, AdapterHealth, PerformanceMetric } from "@/api/types";
import { mockSystemHealth, mockAdapters, mockPerformanceMetrics } from "@/mock/mockData";
import * as gateway from "@/api/gateway";

const DEV_MODE = import.meta.env.DEV;

export function useSystemHealth() {
  const [layers, setLayers] = useState<LayerHealth[]>(DEV_MODE ? mockSystemHealth : []);
  const [adapters, setAdapters] = useState<AdapterHealth[]>(DEV_MODE ? mockAdapters : []);
  const [metrics, setMetrics] = useState<PerformanceMetric[]>(DEV_MODE ? mockPerformanceMetrics : []);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (DEV_MODE) return;
    async function fetch() {
      setLoading(true);
      try {
        const [h, a, m] = await Promise.all([gateway.getSystemHealth(), gateway.getAdapterStatus(), gateway.getPerformanceMetrics()]);
        setLayers(h); setAdapters(a); setMetrics(m);
      } catch {}
      finally { setLoading(false); }
    }
    void fetch();
    const interval = setInterval(() => void fetch(), 30_000);
    return () => clearInterval(interval);
  }, []);

  return { layers, adapters, metrics, loading };
}
