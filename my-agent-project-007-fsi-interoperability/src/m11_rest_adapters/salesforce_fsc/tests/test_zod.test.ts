/**
 * Zod input validation tests. Spec AC8.1, AC8.3, AC8.4, AC8.9.
 */

import { describe, it, expect } from "vitest";

import {
  CreateInteractionSummaryInput,
  FetchClientInput,
  FetchGoalInput,
  FetchHouseholdInput,
  UpdateClientInput,
} from "../src/schemas.js";

const VALID_ID_15 = "001A00000123456";
const VALID_ID_18 = "001A000001234567AA";

describe("SFDC id regex — 15 or 18 base62", () => {
  it.each([VALID_ID_15, VALID_ID_18])("accepts %s", (id) => {
    expect(FetchClientInput.safeParse({ clientId: id }).success).toBe(true);
  });
  it.each([
    "",
    "too-short",
    "001A00000123456AA123456789",
    "001A0000012345!",
    "has space",
    "001A00000ñ1234567",
  ])("rejects %s", (id) => {
    expect(FetchClientInput.safeParse({ clientId: id }).success).toBe(false);
  });
});

describe("UpdateClientInput — AC8.9 ifMatch required", () => {
  it("requires ifMatch", () => {
    expect(
      UpdateClientInput.safeParse({
        clientId: VALID_ID_18,
        fields: { FinServ__Status__c: "Active" },
      }).success,
    ).toBe(false);
  });

  it("accepts writable fields", () => {
    expect(
      UpdateClientInput.safeParse({
        clientId: VALID_ID_18,
        ifMatch: `"W/\\"3-abc123\\""`,
        fields: {
          FinServ__Status__c: "Inactive",
          Description: "test",
        },
      }).success,
    ).toBe(true);
  });

  it("rejects PII fields (writable allow-list)", () => {
    const res = UpdateClientInput.safeParse({
      clientId: VALID_ID_18,
      ifMatch: "etag-1",
      fields: { FirstName: "Jane", LastName: "Doe", Email: "jane@example.com" },
    });
    expect(res.success).toBe(false);
  });

  it("caps Description at 4000 chars", () => {
    const res = UpdateClientInput.safeParse({
      clientId: VALID_ID_18,
      ifMatch: "etag-1",
      fields: { Description: "x".repeat(4001) },
    });
    expect(res.success).toBe(false);
  });
});

describe("CreateInteractionSummaryInput — writeback with ETag", () => {
  it("requires ifMatch + summary + date", () => {
    expect(
      CreateInteractionSummaryInput.safeParse({
        clientId: VALID_ID_18,
        summaryText: "Call notes",
        interactionDate: "2026-05-05",
      }).success,
    ).toBe(false);
  });

  it("caps summary at 32000 chars", () => {
    expect(
      CreateInteractionSummaryInput.safeParse({
        clientId: VALID_ID_18,
        ifMatch: "etag-1",
        summaryText: "x".repeat(32_001),
        interactionDate: "2026-05-05",
      }).success,
    ).toBe(false);
  });

  it("rejects malformed date", () => {
    expect(
      CreateInteractionSummaryInput.safeParse({
        clientId: VALID_ID_18,
        ifMatch: "etag-1",
        summaryText: "notes",
        interactionDate: "05/05/2026",
      }).success,
    ).toBe(false);
  });

  it("accepts valid interactionType enum", () => {
    for (const t of ["meeting", "call", "email", "note", "task"] as const) {
      expect(
        CreateInteractionSummaryInput.safeParse({
          clientId: VALID_ID_18,
          ifMatch: "etag-1",
          summaryText: "n",
          interactionDate: "2026-05-05",
          interactionType: t,
        }).success,
      ).toBe(true);
    }
  });
});

describe("Household + Goal schemas", () => {
  it("householdId follows same regex", () => {
    expect(FetchHouseholdInput.safeParse({ householdId: VALID_ID_18 }).success).toBe(
      true,
    );
    expect(FetchHouseholdInput.safeParse({ householdId: "short" }).success).toBe(
      false,
    );
  });
  it("goalId follows same regex", () => {
    expect(FetchGoalInput.safeParse({ goalId: VALID_ID_18 }).success).toBe(true);
  });
});
