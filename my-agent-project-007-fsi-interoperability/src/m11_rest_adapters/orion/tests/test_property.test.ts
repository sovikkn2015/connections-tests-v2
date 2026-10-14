import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

import {
  FetchHoldingsInput,
  FetchHouseholdInput,
  FetchTransactionsInput,
} from "../src/schemas.js";

function rate<T>(gen: fc.Arbitrary<T>, pred: (v: T) => boolean, runs = 500): number {
  let pass = 0;
  fc.assert(
    fc.property(gen, (v) => {
      if (pred(v)) pass++;
      return true;
    }),
    { numRuns: runs, seed: 77 },
  );
  return pass / runs;
}

describe("orion.fetch_holdings property", () => {
  it("accepts in-domain >= 99%", () => {
    const gen = fc.record({ accountId: fc.integer({ min: 1, max: 10_000_000 }) });
    expect(rate(gen, (v) => FetchHoldingsInput.safeParse(v).success)).toBeGreaterThanOrEqual(0.99);
  });
  it("rejects non-positive accountId >= 99%", () => {
    const gen = fc.record({ accountId: fc.integer({ min: -10_000, max: 0 }) });
    expect(rate(gen, (v) => !FetchHoldingsInput.safeParse(v).success)).toBeGreaterThanOrEqual(0.99);
  });
});

describe("orion.fetch_transactions property", () => {
  it("rejects range > 90 days >= 99%", () => {
    const gen = fc
      .tuple(
        fc.date({ min: new Date("2024-01-01"), max: new Date("2024-03-01") }),
        fc.date({ min: new Date("2024-07-01"), max: new Date("2024-12-31") }),
      )
      .map(([a, b]) => ({
        accountId: 1,
        startDate: a.toISOString().slice(0, 10),
        endDate: b.toISOString().slice(0, 10),
      }));
    expect(rate(gen, (v) => !FetchTransactionsInput.safeParse(v).success)).toBeGreaterThanOrEqual(0.99);
  });
});

describe("orion.fetch_household property", () => {
  it("accepts positive int >= 99%", () => {
    const gen = fc.record({ householdId: fc.integer({ min: 1, max: 10_000_000 }) });
    expect(rate(gen, (v) => FetchHouseholdInput.safeParse(v).success)).toBeGreaterThanOrEqual(0.99);
  });
});
