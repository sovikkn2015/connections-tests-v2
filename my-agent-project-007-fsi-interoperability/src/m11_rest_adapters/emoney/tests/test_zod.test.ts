import { describe, it, expect } from "vitest";

import {
  EMONEY_ALLOWLIST_FIELDS,
  EMoneyPlanSummaryOutput,
  FetchPlanSummaryInput,
} from "../src/schemas.js";

const VALID_UUID = "550e8400-e29b-41d4-a716-446655440000";

describe("FetchPlanSummaryInput", () => {
  it("requires UUID planId", () => {
    expect(
      FetchPlanSummaryInput.safeParse({ planId: VALID_UUID }).success,
    ).toBe(true);
  });
  it("rejects non-UUID", () => {
    expect(
      FetchPlanSummaryInput.safeParse({ planId: "not-a-uuid" }).success,
    ).toBe(false);
  });
  it("rejects extra fields", () => {
    expect(
      FetchPlanSummaryInput.safeParse({ planId: VALID_UUID, bad: 1 }).success,
    ).toBe(false);
  });
});

describe("EMoneyPlanSummaryOutput — strict (AC8.5)", () => {
  const MINIMAL = {
    planId: "p-1",
    clientId: "c-1",
    planName: "Retirement v3",
    probabilityOfSuccess: 78.5,
    asOfDate: "2026-04-28",
    createdAt: "2025-01-15T00:00:00Z",
    updatedAt: "2026-04-01T00:00:00Z",
  };

  it("accepts only required 7 fields", () => {
    expect(EMoneyPlanSummaryOutput.safeParse(MINIMAL).success).toBe(true);
  });

  it("accepts all 14 optional fields", () => {
    const full = {
      ...MINIMAL,
      scenarioId: "s-1",
      householdId: "h-1",
      planType: "Retirement",
      totalAssets: 1_250_000,
      totalLiabilities: 180_000,
      retirementGoal: {
        amount: 2_000_000,
        targetDate: "2040-01-01",
        incomeGap: -5_000,
      },
      monteCarlo: { successPct: 78.5, iterations: 10_000 },
      annualSavingsRate: 0.15,
      annualSpending: 80_000,
      socialSecurityEstimate: 36_000,
      pensionIncome: 12_000,
      goalIds: ["g-1", "g-2"],
      assumptions: {
        inflation: 0.03,
        returnAssumption: 0.07,
        lifeExpectancy: 92,
        retirementAge: 67,
        taxRate: 0.24,
      },
      recommendations: [
        { category: "savings", description: "Increase", priority: "high" },
      ],
    };
    expect(EMoneyPlanSummaryOutput.safeParse(full).success).toBe(true);
  });

  it("AC8.6 — rejects rawPlanBody", () => {
    expect(
      EMoneyPlanSummaryOutput.safeParse({
        ...MINIMAL,
        rawPlanBody: "<huge tree>",
      }).success,
    ).toBe(false);
  });

  it("AC8.6 — rejects all 9 forbidden top-level keys", () => {
    for (const bad of [
      "scenariosDetail",
      "cashflowProjection",
      "assumptionsDetail",
      "advisorNotes",
      "clientBalanceSheet",
      "insuranceDetails",
      "taxProjections",
      "estateDetails",
      "monteCarloFullPath",
    ]) {
      expect(
        EMoneyPlanSummaryOutput.safeParse({
          ...MINIMAL,
          [bad]: { anything: true },
        }).success,
      ).toBe(false);
    }
  });

  it("goalIds must be array of strings, NOT objects", () => {
    expect(
      EMoneyPlanSummaryOutput.safeParse({
        ...MINIMAL,
        goalIds: [{ id: "g-1" }],
      }).success,
    ).toBe(false);
    expect(
      EMoneyPlanSummaryOutput.safeParse({ ...MINIMAL, goalIds: ["g-1"] }).success,
    ).toBe(true);
  });

  it("probabilityOfSuccess bounded 0-100", () => {
    for (const bad of [-1, 101]) {
      expect(
        EMoneyPlanSummaryOutput.safeParse({
          ...MINIMAL,
          probabilityOfSuccess: bad,
        }).success,
      ).toBe(false);
    }
  });

  it("planType restricted to enum", () => {
    expect(
      EMoneyPlanSummaryOutput.safeParse({ ...MINIMAL, planType: "Retirement" })
        .success,
    ).toBe(true);
    expect(
      EMoneyPlanSummaryOutput.safeParse({ ...MINIMAL, planType: "Freeform" })
        .success,
    ).toBe(false);
  });
});

describe("EMONEY_ALLOWLIST_FIELDS — 21 total (7+14) per NEW-2", () => {
  it("has exactly 7 required + 14 optional = 21", () => {
    expect(EMONEY_ALLOWLIST_FIELDS.length).toBe(21);
    expect(new Set(EMONEY_ALLOWLIST_FIELDS).size).toBe(21);
  });
});
