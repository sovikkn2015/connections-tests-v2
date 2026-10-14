/** Orion Zod schemas — spec §Design T-OR1..T-OR4. */

import { z } from "zod";

const PositiveInt = z.number().int().positive();
const IsoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

function daysBetween(a: string, b: string): number {
  const aMs = Date.parse(a);
  const bMs = Date.parse(b);
  if (!Number.isFinite(aMs) || !Number.isFinite(bMs)) return Number.MAX_SAFE_INTEGER;
  return Math.abs(bMs - aMs) / 86_400_000;
}

function todayUtcIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export const FetchHoldingsInput = z
  .object({
    accountId: PositiveInt,
    asOfDate: IsoDate.optional(),
  })
  .strict()
  .refine((v) => !v.asOfDate || v.asOfDate <= todayUtcIso(), {
    message: "asOfDate_future",
    path: ["asOfDate"],
  });

export const FetchTransactionsInput = z
  .object({
    accountId: PositiveInt,
    startDate: IsoDate,
    endDate: IsoDate,
  })
  .strict()
  .refine((v) => daysBetween(v.startDate, v.endDate) <= 90, {
    message: "range_gt_90_days",
    path: ["endDate"],
  })
  .refine((v) => v.startDate <= v.endDate, {
    message: "start_after_end",
    path: ["startDate"],
  });

export const FetchHouseholdInput = z
  .object({ householdId: PositiveInt })
  .strict();

export const FetchTaxlotsInput = z
  .object({
    accountId: PositiveInt,
    asOfDate: IsoDate.optional(),
  })
  .strict();

export type FetchHoldingsArgs = z.infer<typeof FetchHoldingsInput>;
export type FetchTransactionsArgs = z.infer<typeof FetchTransactionsInput>;
export type FetchHouseholdArgs = z.infer<typeof FetchHouseholdInput>;
export type FetchTaxlotsArgs = z.infer<typeof FetchTaxlotsInput>;
