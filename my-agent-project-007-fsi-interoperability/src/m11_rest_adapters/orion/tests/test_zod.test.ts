import { describe, it, expect } from "vitest";
import {
  FetchHoldingsInput,
  FetchHouseholdInput,
  FetchTaxlotsInput,
  FetchTransactionsInput,
} from "../src/schemas.js";

describe("Orion fetch_holdings", () => {
  it("accepts positive accountId + valid asOfDate", () => {
    expect(
      FetchHoldingsInput.safeParse({ accountId: 12345, asOfDate: "2025-01-15" }).success,
    ).toBe(true);
  });
  it("rejects negative accountId", () => {
    expect(FetchHoldingsInput.safeParse({ accountId: -1 }).success).toBe(false);
  });
  it("rejects asOfDate in the future", () => {
    const future = new Date(Date.now() + 10 * 86_400_000).toISOString().slice(0, 10);
    expect(
      FetchHoldingsInput.safeParse({ accountId: 1, asOfDate: future }).success,
    ).toBe(false);
  });
  it("rejects extra fields", () => {
    expect(FetchHoldingsInput.safeParse({ accountId: 1, extra: "bad" }).success).toBe(false);
  });
});

describe("Orion fetch_transactions", () => {
  it("accepts a range <= 90 days", () => {
    expect(
      FetchTransactionsInput.safeParse({ accountId: 1, startDate: "2026-01-01", endDate: "2026-03-15" }).success,
    ).toBe(true);
  });
  it("rejects a range > 90 days", () => {
    expect(
      FetchTransactionsInput.safeParse({ accountId: 1, startDate: "2026-01-01", endDate: "2026-06-01" }).success,
    ).toBe(false);
  });
  it("rejects start > end", () => {
    expect(
      FetchTransactionsInput.safeParse({ accountId: 1, startDate: "2026-03-15", endDate: "2026-01-01" }).success,
    ).toBe(false);
  });
});

describe("Orion fetch_household + fetch_taxlots", () => {
  it("householdId must be positive", () => {
    expect(FetchHouseholdInput.safeParse({ householdId: 42 }).success).toBe(true);
    expect(FetchHouseholdInput.safeParse({ householdId: 0 }).success).toBe(false);
  });
  it("taxlots accepts asOfDate", () => {
    expect(
      FetchTaxlotsInput.safeParse({ accountId: 1, asOfDate: "2026-01-15" }).success,
    ).toBe(true);
  });
});
