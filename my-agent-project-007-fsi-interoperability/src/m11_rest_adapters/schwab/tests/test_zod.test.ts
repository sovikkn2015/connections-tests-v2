import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

import {
  FetchMasterAccountInput,
  FetchPositionsInput,
  FetchTaxlotsInput,
} from "../src/schemas.js";

describe("Schwab accountNumber regex — 8 digits", () => {
  it("accepts 8 digits", () => {
    expect(FetchPositionsInput.safeParse({ accountNumber: "12345678" }).success).toBe(true);
  });
  it.each(["1234567", "123456789", "abc12345", "12 34 56 78"])("rejects %s", (n) => {
    expect(FetchPositionsInput.safeParse({ accountNumber: n }).success).toBe(false);
  });
});

describe("Schwab fetch_taxlots symbol regex", () => {
  it("accepts valid tickers", () => {
    for (const s of ["AAPL", "BRK.A", "BRK-B", "SPY"]) {
      expect(
        FetchTaxlotsInput.safeParse({ accountNumber: "12345678", symbol: s }).success,
      ).toBe(true);
    }
  });
  it("rejects lowercase", () => {
    expect(
      FetchTaxlotsInput.safeParse({ accountNumber: "12345678", symbol: "aapl" }).success,
    ).toBe(false);
  });
  it("rejects symbol > 20 chars", () => {
    expect(
      FetchTaxlotsInput.safeParse({ accountNumber: "12345678", symbol: "A".repeat(21) }).success,
    ).toBe(false);
  });
});

describe("Schwab fetch_master_account id regex", () => {
  it("accepts uppercase + digits + dashes up to 32 chars", () => {
    expect(FetchMasterAccountInput.safeParse({ masterAccountId: "MA-ABC-123" }).success).toBe(true);
  });
  it("rejects lowercase", () => {
    expect(FetchMasterAccountInput.safeParse({ masterAccountId: "ma-abc-123" }).success).toBe(false);
  });
  it("rejects > 32 chars", () => {
    expect(
      FetchMasterAccountInput.safeParse({ masterAccountId: "A".repeat(33) }).success,
    ).toBe(false);
  });
});

describe("Property-based — accountNumber", () => {
  it("accepts 8-digit >= 99%", () => {
    const gen = fc
      .array(fc.integer({ min: 0, max: 9 }), { minLength: 8, maxLength: 8 })
      .map((arr) => arr.join(""));
    let pass = 0;
    const runs = 500;
    fc.assert(
      fc.property(gen, (n) => {
        if (FetchPositionsInput.safeParse({ accountNumber: n }).success) pass++;
        return true;
      }),
      { numRuns: runs, seed: 13 },
    );
    expect(pass / runs).toBeGreaterThanOrEqual(0.99);
  });
});
