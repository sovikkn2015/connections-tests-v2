/**
 * Smarsh Zod input-validation tests — 16 cases across 5 tools.
 * Spec AC-SM2 + AC-SM3 + AC-SM4.
 */

import { describe, it, expect } from "vitest";

import {
  ArchiveCaptureInput,
  ArchiveMessageInput,
  GetCaptureStatusInput,
  RetrieveMessageInput,
  SearchMessagesInput,
} from "../src/schemas.js";

const VALID_UUID = "550e8400-e29b-41d4-a716-446655440000";
const VALID_UUID_2 = "7c9e6679-7425-40de-944b-e07fc1f90ae7";
const NOW = "2026-05-20T12:00:00Z";

/** Build a valid archive_message payload; pass overrides to mutate specific fields. */
function archiveMsg(overrides: Record<string, unknown> = {}): unknown {
  return {
    messageId: VALID_UUID,
    channel: "email",
    participants: [{ role: "advisor", identifier: "adv-001" }],
    content: "Hello client",
    contentType: "text/plain",
    timestamp: NOW,
    retentionTier: "regulatory_7yr",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// archive_message (AC-SM2 / AC-SM3 / AC-SM4)
// ---------------------------------------------------------------------------

describe("ArchiveMessageInput", () => {
  it("AC-SM2 case 1 — accepts valid minimal payload", () => {
    expect(ArchiveMessageInput.safeParse(archiveMsg()).success).toBe(true);
  });

  it("AC-SM2 case 2 — rejects content > 1 MiB", () => {
    const oversize = "a".repeat(1_048_577);
    expect(
      ArchiveMessageInput.safeParse(archiveMsg({ content: oversize })).success,
    ).toBe(false);
  });

  it("AC-SM2 case 3 — rejects non-UUID messageId", () => {
    expect(
      ArchiveMessageInput.safeParse(archiveMsg({ messageId: "not-a-uuid" }))
        .success,
    ).toBe(false);
  });

  it("AC-SM2 case 4 — rejects unknown channel", () => {
    expect(
      ArchiveMessageInput.safeParse(archiveMsg({ channel: "fax" })).success,
    ).toBe(false);
  });

  it("AC-SM3 case 5 — rejects unknown retention tier", () => {
    expect(
      ArchiveMessageInput.safeParse(archiveMsg({ retentionTier: "forever" }))
        .success,
    ).toBe(false);
  });

  it("AC-SM3 case 5b — accepts all three retention tier enum values", () => {
    for (const tier of [
      "regulatory_3yr",
      "regulatory_7yr",
      "regulatory_permanent",
    ]) {
      expect(
        ArchiveMessageInput.safeParse(archiveMsg({ retentionTier: tier }))
          .success,
      ).toBe(true);
    }
  });

  it("AC-SM2 case 6 — rejects empty participants array", () => {
    expect(
      ArchiveMessageInput.safeParse(archiveMsg({ participants: [] })).success,
    ).toBe(false);
  });

  it("AC-SM4 case 7 — rejects legalHold:true (C4 legal-hold deferral)", () => {
    const parsed = ArchiveMessageInput.safeParse(
      archiveMsg({ legalHold: true }),
    );
    expect(parsed.success).toBe(false);
    if (!parsed.success) {
      const msgs = parsed.error.issues.map((i) => i.message).join("|");
      // Strict() fires first with "Unrecognized key(s)" for any unknown top-level
      // key; the .superRefine then adds our targeted message. Either is acceptable
      // — the tool call is rejected as invalid_arguments at the MCP layer regardless.
      expect(
        msgs.includes("legal_hold_not_implemented_v1") ||
          /unrecognized|legalHold/i.test(msgs),
      ).toBe(true);
    }
  });

  it("rejects extra top-level keys (strict)", () => {
    expect(
      ArchiveMessageInput.safeParse(archiveMsg({ rogueField: "x" })).success,
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// retrieve_message + search_messages
// ---------------------------------------------------------------------------

describe("RetrieveMessageInput", () => {
  it("AC-SM2 case 8 — accepts a vendor-shaped archiveId", () => {
    expect(
      RetrieveMessageInput.safeParse({ archiveId: "SM-2026-05-01-abc123" })
        .success,
    ).toBe(true);
  });
  it("AC-SM2 case 9 — rejects archiveId with bad chars / length", () => {
    expect(
      RetrieveMessageInput.safeParse({ archiveId: "bad id with spaces" })
        .success,
    ).toBe(false);
    expect(
      RetrieveMessageInput.safeParse({ archiveId: "short" }).success,
    ).toBe(false);
  });
});

describe("SearchMessagesInput", () => {
  it("AC-SM2 case 10 — rejects window > 90 days", () => {
    expect(
      SearchMessagesInput.safeParse({
        startTime: "2026-01-01T00:00:00Z",
        endTime: "2026-06-01T00:00:00Z",
      }).success,
    ).toBe(false);
  });
  it("AC-SM2 case 11 — rejects start > end", () => {
    expect(
      SearchMessagesInput.safeParse({
        startTime: "2026-06-01T00:00:00Z",
        endTime: "2026-01-01T00:00:00Z",
      }).success,
    ).toBe(false);
  });
  it("accepts a 30-day bounded window", () => {
    expect(
      SearchMessagesInput.safeParse({
        startTime: "2026-01-01T00:00:00Z",
        endTime: "2026-01-31T00:00:00Z",
        pageSize: 50,
      }).success,
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// archive_capture (Connected Archive — HMAC-signed)
// ---------------------------------------------------------------------------

const B64_HELLO = "aGVsbG8gd29ybGQ="; // "hello world"

function capture(overrides: Record<string, unknown> = {}): unknown {
  return {
    captureId: VALID_UUID,
    fileName: "statement-2026-05.pdf",
    mimeType: "application/pdf",
    contentBase64: B64_HELLO,
    capturedAt: NOW,
    retentionTier: "regulatory_7yr",
    ...overrides,
  };
}

describe("ArchiveCaptureInput", () => {
  it("accepts a well-formed capture", () => {
    expect(ArchiveCaptureInput.safeParse(capture()).success).toBe(true);
  });
  it("rejects path-traversal in fileName (C5)", () => {
    expect(
      ArchiveCaptureInput.safeParse(capture({ fileName: "../../etc/passwd" }))
        .success,
    ).toBe(false);
  });
  it("rejects NUL byte in fileName (C5)", () => {
    expect(
      ArchiveCaptureInput.safeParse(capture({ fileName: "bad\0.pdf" })).success,
    ).toBe(false);
  });
  it("rejects malformed mimeType (not RFC 6838)", () => {
    expect(
      ArchiveCaptureInput.safeParse(capture({ mimeType: "not-a-mime" })).success,
    ).toBe(false);
  });
  it("rejects url-safe base64 (must use standard alphabet)", () => {
    expect(
      ArchiveCaptureInput.safeParse(
        capture({ contentBase64: "aGVsbG8td29ybGQ_" }),
      ).success,
    ).toBe(false);
  });
  it("rejects unpadded base64 (len % 4 != 0)", () => {
    expect(
      ArchiveCaptureInput.safeParse(capture({ contentBase64: "aGVsbG8" })).success,
    ).toBe(false);
  });
  it("accepts optional relatedMessageId UUID", () => {
    expect(
      ArchiveCaptureInput.safeParse(
        capture({ relatedMessageId: VALID_UUID_2 }),
      ).success,
    ).toBe(true);
  });
});

describe("GetCaptureStatusInput", () => {
  it("accepts a UUID captureId", () => {
    expect(
      GetCaptureStatusInput.safeParse({ captureId: VALID_UUID }).success,
    ).toBe(true);
  });
  it("rejects a non-UUID captureId", () => {
    expect(
      GetCaptureStatusInput.safeParse({ captureId: "abc" }).success,
    ).toBe(false);
  });
});
