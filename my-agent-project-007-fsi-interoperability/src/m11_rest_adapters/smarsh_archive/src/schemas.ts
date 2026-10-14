/**
 * Smarsh Zod schemas + SEC 17a-4 retention-tier enum.
 * Spec §5 + AC-SM2/3/4.
 */

import { z } from "zod";

/** SEC 17a-4 retention tiers (spec §6). Values == vendor `retention_policy` strings. */
export const SmarshRetentionTier = z.enum([
  "regulatory_3yr", // 17a-4(b)(4) internal / FINRA 2210 correspondence
  "regulatory_7yr", // 17a-4(b)(1-2) books & records — default for client comms
  "regulatory_permanent", // 17a-4(a) firm formation / partnership agreements
]);
export type SmarshRetentionTier = z.infer<typeof SmarshRetentionTier>;

/** Communication channels the adapter accepts (spec §5.1). */
export const SmarshChannel = z.enum([
  "email",
  "chat",
  "sms",
  "voice_transcript",
  "agent_output",
]);
export type SmarshChannel = z.infer<typeof SmarshChannel>;

/** Participant reference — role + opaque identifier (spec §5.1 / E1 512-char max). */
export const ParticipantRef = z
  .object({
    role: z.enum(["advisor", "client", "agent", "principal", "cc"]),
    identifier: z.string().min(1).max(512),
  })
  .strict();
export type ParticipantRef = z.infer<typeof ParticipantRef>;

/**
 * archive_message input.
 *
 * C4 — `legalHold` is explicitly rejected. Callers must not silently pass it —
 * legal-hold lifecycle is a v2 feature. Any truthy value → `invalid_arguments`.
 */
export const ArchiveMessageInput = z
  .object({
    messageId: z.string().uuid(),
    channel: SmarshChannel,
    participants: z.array(ParticipantRef).min(1).max(100),
    content: z.string().min(1).max(1_048_576), // 1 MiB ceiling (matches Fastify body limit)
    contentType: z.enum(["text/plain", "text/html", "application/json"]),
    timestamp: z.string().datetime(), // ISO 8601 UTC with Z
    retentionTier: SmarshRetentionTier,
    metadata: z.record(z.string().max(64), z.string().max(256)).optional(),
  })
  .strict()
  .superRefine((val, ctx) => {
    // C4 — explicit legal-hold rejection. `.strict()` blocks unknown keys at top level,
    // but Zod's unknown-key pass yields `unrecognized_keys` which callers may shrug off.
    // Emit a targeted code so the rejection reason is crystal clear.
    const anyVal = val as Record<string, unknown>;
    if (Object.prototype.hasOwnProperty.call(anyVal, "legalHold")) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["legalHold"],
        message: "legal_hold_not_implemented_v1",
      });
    }
  });
export type ArchiveMessageArgs = z.infer<typeof ArchiveMessageInput>;

/** retrieve_message input — archiveId is vendor-issued opaque string. */
export const RetrieveMessageInput = z
  .object({
    archiveId: z.string().regex(/^[A-Za-z0-9_\-]{8,64}$/),
  })
  .strict();
export type RetrieveMessageArgs = z.infer<typeof RetrieveMessageInput>;

/** search_messages input — bounded ≤ 90 day window. */
export const SearchMessagesInput = z
  .object({
    participantIdentifier: z.string().min(1).max(512).optional(),
    channel: SmarshChannel.optional(),
    startTime: z.string().datetime(),
    endTime: z.string().datetime(),
    pageSize: z.number().int().positive().max(100).optional(),
    pageToken: z.string().max(512).optional(),
  })
  .strict()
  .refine((v) => Date.parse(v.startTime) <= Date.parse(v.endTime), {
    message: "start_after_end",
    path: ["startTime"],
  })
  .refine(
    (v) =>
      Date.parse(v.endTime) - Date.parse(v.startTime) <= 90 * 86_400_000,
    { message: "range_gt_90_days", path: ["endTime"] },
  );
export type SearchMessagesArgs = z.infer<typeof SearchMessagesInput>;

// -----------------------------------------------------------------------------
// Connected Archive tools (HMAC-signed) — spec §5.4 / §5.5 (Phase 3 addendum).
// -----------------------------------------------------------------------------

/**
 * archive_capture input — attachment upload to `POST /api/v1/captures`.
 *
 * `contentBase64` is the standard-alphabet, `=`-padded base64 of the raw attachment
 * bytes. 1 MiB ceiling aligns with Fastify body limit (AC1.8) — a 1 MiB attachment
 * becomes ~1.37 MiB of JSON request body which still fits our route cap once metadata
 * is kept small.
 */
export const ArchiveCaptureInput = z
  .object({
    captureId: z.string().uuid(),
    fileName: z
      .string()
      .min(1)
      .max(256)
      // C5 — reject path-traversal & NUL.
      .regex(/^[^/\\\0]+$/, { message: "fileName_invalid_chars" }),
    mimeType: z
      .string()
      .min(1)
      .max(128)
      .regex(/^[a-zA-Z0-9][a-zA-Z0-9!#$&^_.+-]*\/[a-zA-Z0-9!#$&^_.+-]+$/, {
        message: "mimeType_not_rfc6838",
      }),
    // Strict base64 standard alphabet (no URL-safe chars); `=` padded.
    contentBase64: z
      .string()
      .min(4)
      .max(1_400_000) // ~1.05 MiB raw
      .regex(/^[A-Za-z0-9+/]+={0,2}$/, { message: "contentBase64_invalid" }),
    capturedAt: z.string().datetime(),
    relatedMessageId: z.string().uuid().optional(),
    retentionTier: SmarshRetentionTier,
    metadata: z.record(z.string().max(64), z.string().max(256)).optional(),
  })
  .strict()
  .refine((v) => v.contentBase64.length % 4 === 0, {
    message: "contentBase64_not_padded",
    path: ["contentBase64"],
  });
export type ArchiveCaptureArgs = z.infer<typeof ArchiveCaptureInput>;

/**
 * get_capture_status input — retrieves processing state of a previously-uploaded
 * attachment. Vendor path: `GET /api/v1/captures/{id}/status`.
 */
export const GetCaptureStatusInput = z
  .object({
    captureId: z.string().uuid(),
  })
  .strict();
export type GetCaptureStatusArgs = z.infer<typeof GetCaptureStatusInput>;
