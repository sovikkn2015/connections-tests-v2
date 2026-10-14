import { useState, useCallback, useEffect } from "react";
import type { ReviewItem } from "@/api/types";
import { mockReviewQueue } from "@/mock/mockData";
import * as gateway from "@/api/gateway";

const DEV_MODE = import.meta.env.DEV;

export function useReviewQueue() {
  const [items, setItems] = useState<ReviewItem[]>(DEV_MODE ? mockReviewQueue : []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (DEV_MODE) return;
    setLoading(true);
    gateway.getReviewQueue().then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const selected = items.find((i) => i.id === selectedId) ?? null;
  const select = useCallback((item: ReviewItem) => setSelectedId(item.id), []);

  const approve = useCallback(async (id: string) => {
    if (!DEV_MODE) await gateway.submitReviewAction({ reviewId: id, action: "approve" });
    setItems((prev) => prev.filter((i) => i.id !== id));
    setSelectedId(null);
  }, []);

  const reject = useCallback(async (id: string, reason: string) => {
    if (!DEV_MODE) await gateway.submitReviewAction({ reviewId: id, action: "reject", reason });
    setItems((prev) => prev.filter((i) => i.id !== id));
    setSelectedId(null);
  }, []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const idx = items.findIndex((i) => i.id === selectedId);
      if (e.key === "ArrowDown" && idx < items.length - 1) setSelectedId(items[idx + 1]!.id);
      else if (e.key === "ArrowUp" && idx > 0) setSelectedId(items[idx - 1]!.id);
      else if ((e.key === "a" || e.key === "A") && selectedId) void approve(selectedId);
      else if ((e.key === "r" || e.key === "R") && selectedId) void reject(selectedId, "Rejected via keyboard shortcut");
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [items, selectedId, approve, reject]);

  return { items, selected, selectedId, select, approve, reject, loading };
}
