/**
 * Property-based Zod fuzz tests for SFDC tools. Spec AC18.6.
 */

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

import {
  FetchClientInput,
  FetchGoalInput,
  FetchHouseholdInput,
  UpdateClientInput,
} from "../src/schemas.js";

const ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

const inDomainSfdcId = fc
  .integer({ min: 15, max: 18 })
  .chain((len) =>
    fc
      .array(
        fc.integer({ min: 0, max: ALPHABET.length - 1 }).map((i) => ALPHABET[i]!),
        { minLength: len, maxLength: len },
      )
      .map((arr) => arr.join("")),
  );

const outDomainSfdcId = fc.oneof(
  fc.string({ minLength: 0, maxLength: 14 }),
  fc.string({ minLength: 19, maxLength: 40 }),
  fc.constantFrom("", " ", "dash-has-dash", "ñÑsoft", "emoji😀here"),
);

function rate<T>(
  gen: fc.Arbitrary<T>,
  predicate: (v: T) => boolean,
  runs: number = 1000,
): number {
  let pass = 0;
  fc.assert(
    fc.property(gen, (v) => {
      if (predicate(v)) pass++;
      return true;
    }),
    { numRuns: runs, seed: 42 },
  );
  return pass / runs;
}

describe("AC18.6 — sfdc.fetch_client property", () => {
  it("accepts in-domain clientId ≥ 99%", () => {
    const r = rate(
      inDomainSfdcId,
      (id) => FetchClientInput.safeParse({ clientId: id }).success,
    );
    expect(r).toBeGreaterThanOrEqual(0.99);
  });

  it("rejects out-of-domain clientId ≥ 99%", () => {
    const r = rate(
      outDomainSfdcId,
      (id) => !FetchClientInput.safeParse({ clientId: id }).success,
    );
    expect(r).toBeGreaterThanOrEqual(0.99);
  });
});

describe("AC18.6 — sfdc.fetch_household property", () => {
  it("accepts in-domain ≥ 99%", () => {
    const r = rate(
      inDomainSfdcId,
      (id) => FetchHouseholdInput.safeParse({ householdId: id }).success,
    );
    expect(r).toBeGreaterThanOrEqual(0.99);
  });
});

describe("AC18.6 — sfdc.fetch_goal property", () => {
  it("accepts in-domain ≥ 99%", () => {
    const r = rate(
      inDomainSfdcId,
      (id) => FetchGoalInput.safeParse({ goalId: id }).success,
    );
    expect(r).toBeGreaterThanOrEqual(0.99);
  });
});

describe("AC18.6 — sfdc.update_client property", () => {
  const inDomainUpdate = fc.record({
    clientId: inDomainSfdcId,
    ifMatch: fc
      .string({ minLength: 1, maxLength: 100 })
      .filter((s) => s.length >= 1),
    fields: fc.record(
      {
        FinServ__Status__c: fc.option(
          fc.string({ minLength: 1, maxLength: 30 }),
          { nil: undefined },
        ),
        Description: fc.option(
          fc.string({ minLength: 0, maxLength: 200 }),
          { nil: undefined },
        ),
      },
      { requiredKeys: [] },
    ),
  });

  it("accepts in-domain update payload ≥ 90%", () => {
    const r = rate(
      inDomainUpdate,
      (v) => UpdateClientInput.safeParse(v).success,
    );
    expect(r).toBeGreaterThanOrEqual(0.9);
  });

  it("rejects missing ifMatch ≥ 99%", () => {
    const r = rate(
      fc.record({
        clientId: inDomainSfdcId,
        fields: fc.record({}, { requiredKeys: [] }),
      }),
      (v) => !UpdateClientInput.safeParse(v).success,
    );
    expect(r).toBeGreaterThanOrEqual(0.99);
  });
});
