/**
 * Smarsh vendor client — 5 tool handlers.
 *
 * Three legacy tools (Professional Archive, OAuth2 Bearer):
 *   - archiveMessage        POST /v1/archive/messages
 *   - retrieveMessage       GET  /v1/archive/messages/{archive_id}
 *   - searchMessages        POST /v1/archive/search
 *
 * Two Connected Archive tools (HMAC-SHA256 body signing, Phase 3 BD):
 *   - archiveCapture        POST /api/v1/captures
 *   - getCaptureStatus      GET  /api/v1/captures/{captureId}/status
 *
 * Spec §5 + AC-SM8 (C1+C2 receipt integrity) + AC-SM15 (audit-on-every-call).
 *
 * Audit contract (verification gate):
 *   Every archive_* handler calls `emitAudit()` exactly once — on success AND on
 *   failure — before returning / re-raising. The audit callback is supplied at
 *   construction time and MUST NOT throw (failures are swallowed to honor
 *   fail-closed business logic).
 *
 * Receipt verify:
 *  - archive_message: local sha256(content) == vendor content_hash, sealed_at within ±5 min
 *  - retrieve_message: local sha256(returned content) == vendor content_hash
 *  - archive_capture: local sha256(raw bytes) == vendor content_hash
 *  - mismatch → vendor_error + severity:"CRITICAL" event smarsh.receipt_mismatch
 *
 * Sha256 hash prefix MUST be exact `sha256:`. Missing `sealed_at` == mismatch.
 * NTP skew logged on every archive.
 */

import { createHash } from "node:crypto";

import {
  AdapterError,
  type Clock,
  type Logger,
  type VendorHttpClient,
} from "@project-007/mcp-sdk";

import type { SmarshAuthClient } from "./auth.js";
import type { SmarshHmacSigner } from "./auth_hmac.js";
import type {
  ArchiveCaptureArgs,
  ArchiveMessageArgs,
  GetCaptureStatusArgs,
  RetrieveMessageArgs,
  SearchMessagesArgs,
} from "./schemas.js";

export type SmarshAuthMode = "oauth2" | "hmac";

/**
 * Audit event emitted to the M10-sidecar channel for every archive_* call.
 * `outcome:"success"` on 2xx + passed receipt-verify; `outcome:"failure"` otherwise.
 *
 * Rule 6 (3-tier WORM) + Rule 20 (no crypto material in logs): we include stable
 * identifiers (archive_id / capture_id / message_id) and the adapter error code
 * but NEVER the request body or credentials.
 */
export interface AdapterAuditEvent {
  readonly event: "smarsh.tool_audit";
  readonly tool: string;
  readonly firm_id: string;
  readonly outcome: "success" | "failure";
  readonly duration_ms: number;
  readonly error_code?: string;
  readonly vendor_status_code?: number | null;
  readonly archive_id?: string;
  readonly capture_id?: string;
  readonly message_id?: string;
}

export interface SmarshClientOptions {
  readonly http: VendorHttpClient;
  readonly clock: Clock;
  readonly logger: Logger;
  readonly apiBaseUrl: string;
  readonly vendorApiVersion: string;
  readonly authMode: SmarshAuthMode;
  /** OAuth2 auth — required when authMode === "oauth2". */
  readonly oauthAuth?: SmarshAuthClient;
  /** HMAC signer — required when authMode === "hmac". */
  readonly hmacSigner?: SmarshHmacSigner;
  /** Called exactly once per archive_* tool invocation — success OR failure. */
  readonly emitAudit?: (ev: AdapterAuditEvent) => void;
}

/** Clock-skew tolerance for vendor sealed_at vs adapter local clock. */
const SEALED_AT_SKEW_MS = 5 * 60_000;
const SEALED_AT_WARN_MS = 60_000;

/** Shape of a Smarsh archive receipt (raw vendor JSON — M7 canonicalizes later). */
interface SmarshArchiveReceipt {
  readonly archive_id: string;
  readonly sealed_at: string;
  readonly retention_expires_at: string;
  readonly content_hash: string;
}

/** Shape of a Smarsh retrieve response. */
interface SmarshRetrievedMessage {
  readonly archive_id: string;
  readonly content: string;
  readonly content_hash: string;
  readonly channel: string;
  readonly timestamp: string;
  readonly retention_policy: string;
  readonly [key: string]: unknown;
}

/** Shape of a Smarsh Connected Archive capture receipt. */
interface SmarshCaptureReceipt {
  readonly capture_id: string;
  readonly sealed_at: string;
  readonly content_hash: string;
  readonly status: string;
  readonly retention_expires_at?: string;
}

/** Shape of a Smarsh Connected Archive status response. */
interface SmarshCaptureStatus {
  readonly capture_id: string;
  readonly status: string;
  readonly updated_at?: string;
  readonly [key: string]: unknown;
}

function sha256Hex(input: string | Uint8Array): string {
  const h = createHash("sha256");
  if (typeof input === "string") h.update(input, "utf8");
  else h.update(input);
  return h.digest("hex");
}

/** Strip the `sha256:` prefix. ANY other prefix (or none) → null (caller treats as mismatch). */
function stripSha256Prefix(hash: unknown): string | null {
  if (typeof hash !== "string") return null;
  const prefix = "sha256:";
  if (!hash.startsWith(prefix)) return null;
  const hex = hash.slice(prefix.length);
  if (!/^[0-9a-f]{64}$/.test(hex)) return null;
  return hex;
}

function safeJson(txt: string): unknown {
  try {
    return JSON.parse(txt);
  } catch {
    throw new AdapterError(
      "vendor_invalid_json",
      "Smarsh returned malformed JSON",
      null,
    );
  }
}

function safeBase64Decode(b64: string): Uint8Array {
  // Zod has already ensured the string is [A-Za-z0-9+/=]+ with correct padding.
  return Buffer.from(b64, "base64");
}

/** Extract the URL path (without host + query) from an absolute URL. */
function pathOf(url: string): string {
  const u = new URL(url);
  return u.pathname;
}

export class SmarshClient {
  constructor(private readonly opts: SmarshClientOptions) {
    if (opts.authMode === "oauth2" && !opts.oauthAuth) {
      throw new Error("SmarshClient: oauth2 mode requires oauthAuth");
    }
    if (opts.authMode === "hmac" && !opts.hmacSigner) {
      throw new Error("SmarshClient: hmac mode requires hmacSigner");
    }
  }

  // ---------------------------------------------------------------------------
  // Header composition — dispatches on authMode.
  // ---------------------------------------------------------------------------

  /**
   * Compose headers for a Bearer (OAuth2) request. Used by legacy tools.
   * `body` is accepted for symmetry with `hmacHeaders` but ignored here.
   */
  private async bearerHeaders(firmId: string): Promise<Record<string, string>> {
    const auth = this.opts.oauthAuth;
    if (!auth) {
      throw new AdapterError(
        "vendor_auth_failed",
        "OAuth2 auth not configured",
        null,
      );
    }
    const h = await auth.headerFor(firmId);
    return {
      ...h,
      accept: "application/json",
      "content-type": "application/json",
    };
  }

  /**
   * Compose headers for an HMAC-signed request. Used by Connected Archive tools.
   * Body MUST be the exact bytes the client will send (empty string for GET).
   */
  private async hmacHeaders(
    method: string,
    url: string,
    body: string,
  ): Promise<Record<string, string>> {
    const signer = this.opts.hmacSigner;
    if (!signer) {
      throw new AdapterError(
        "vendor_auth_failed",
        "HMAC signer not configured",
        null,
      );
    }
    const signed = await signer.sign({ method, path: pathOf(url), body });
    return {
      ...signed,
      accept: "application/json",
      ...(method.toUpperCase() === "GET"
        ? {}
        : { "content-type": "application/json" }),
    };
  }

  /** Non-throwing audit emit. */
  private audit(ev: AdapterAuditEvent): void {
    try {
      this.opts.emitAudit?.(ev);
    } catch (err) {
      this.opts.logger.warn({
        event: "smarsh.audit_emit_failed",
        err: err instanceof Error ? err.message : String(err),
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Legacy Professional Archive tools (OAuth2).
  // ---------------------------------------------------------------------------

  async archiveMessage(
    args: ArchiveMessageArgs,
    firmId: string,
  ): Promise<unknown> {
    const startedAt = this.opts.clock.now();
    const v = this.opts.vendorApiVersion;
    const url = `${this.opts.apiBaseUrl}/${v}/archive/messages`;
    const body = JSON.stringify({
      message_id: args.messageId,
      channel: args.channel,
      participants: args.participants,
      content: args.content,
      content_type: args.contentType,
      timestamp: args.timestamp,
      retention_policy: args.retentionTier,
      ...(args.metadata ? { metadata: args.metadata } : {}),
    });

    try {
      const res = await this.callBearer(firmId, {
        method: "POST",
        url,
        body,
        toolName: "smarsh.archive_message",
      });
      const parsed = safeJson(res.bodyText) as SmarshArchiveReceipt;
      this.verifyArchiveReceipt(parsed, args.content, firmId);
      this.audit({
        event: "smarsh.tool_audit",
        tool: "smarsh.archive_message",
        firm_id: firmId,
        outcome: "success",
        duration_ms: this.opts.clock.now() - startedAt,
        vendor_status_code: res.status,
        archive_id: parsed.archive_id,
        message_id: args.messageId,
      });
      return parsed;
    } catch (err) {
      this.auditFailure(
        "smarsh.archive_message",
        firmId,
        startedAt,
        err,
        { message_id: args.messageId },
      );
      throw err;
    }
  }

  async retrieveMessage(
    args: RetrieveMessageArgs,
    firmId: string,
  ): Promise<unknown> {
    const v = this.opts.vendorApiVersion;
    const url = `${this.opts.apiBaseUrl}/${v}/archive/messages/${encodeURIComponent(args.archiveId)}`;
    const res = await this.callBearer(firmId, {
      method: "GET",
      url,
      toolName: "smarsh.retrieve_message",
    });
    const parsed = safeJson(res.bodyText) as SmarshRetrievedMessage;
    this.verifyRetrievedHash(parsed, firmId);
    return parsed;
  }

  async searchMessages(
    args: SearchMessagesArgs,
    firmId: string,
  ): Promise<unknown> {
    const v = this.opts.vendorApiVersion;
    const url = `${this.opts.apiBaseUrl}/${v}/archive/search`;
    const payload: Record<string, unknown> = {
      start_time: args.startTime,
      end_time: args.endTime,
    };
    if (args.participantIdentifier !== undefined) {
      payload["participant_identifier"] = args.participantIdentifier;
    }
    if (args.channel !== undefined) payload["channel"] = args.channel;
    if (args.pageSize !== undefined) payload["page_size"] = args.pageSize;
    if (args.pageToken !== undefined) payload["page_token"] = args.pageToken;

    const res = await this.callBearer(firmId, {
      method: "POST",
      url,
      body: JSON.stringify(payload),
      toolName: "smarsh.search_messages",
    });
    return safeJson(res.bodyText);
  }

  // ---------------------------------------------------------------------------
  // Connected Archive tools (HMAC).
  // ---------------------------------------------------------------------------

  /**
   * POST /api/v1/captures — upload an attachment + verify sealed receipt.
   *
   * HMAC-signed; Body is a JSON envelope around the base64 content. Receipt verify
   * recomputes sha256 over the RAW decoded bytes (not the base64 string), so a
   * downstream-recoded base64 that decodes to the same bytes still verifies.
   */
  async archiveCapture(
    args: ArchiveCaptureArgs,
    firmId: string,
  ): Promise<unknown> {
    const startedAt = this.opts.clock.now();
    const url = `${this.opts.apiBaseUrl}/api/${this.opts.vendorApiVersion}/captures`;
    const body = JSON.stringify({
      capture_id: args.captureId,
      file_name: args.fileName,
      mime_type: args.mimeType,
      content_base64: args.contentBase64,
      captured_at: args.capturedAt,
      retention_policy: args.retentionTier,
      ...(args.relatedMessageId ? { related_message_id: args.relatedMessageId } : {}),
      ...(args.metadata ? { metadata: args.metadata } : {}),
    });

    try {
      const res = await this.callHmac(firmId, {
        method: "POST",
        url,
        body,
        toolName: "smarsh.archive_capture",
      });
      const parsed = safeJson(res.bodyText) as SmarshCaptureReceipt;
      const rawBytes = safeBase64Decode(args.contentBase64);
      this.verifyCaptureReceipt(parsed, rawBytes, firmId);
      this.audit({
        event: "smarsh.tool_audit",
        tool: "smarsh.archive_capture",
        firm_id: firmId,
        outcome: "success",
        duration_ms: this.opts.clock.now() - startedAt,
        vendor_status_code: res.status,
        capture_id: parsed.capture_id,
      });
      return parsed;
    } catch (err) {
      this.auditFailure(
        "smarsh.archive_capture",
        firmId,
        startedAt,
        err,
        { capture_id: args.captureId },
      );
      throw err;
    }
  }

  /** GET /api/v1/captures/{id}/status — HMAC-signed, no body. */
  async getCaptureStatus(
    args: GetCaptureStatusArgs,
    firmId: string,
  ): Promise<unknown> {
    const startedAt = this.opts.clock.now();
    const url = `${this.opts.apiBaseUrl}/api/${this.opts.vendorApiVersion}/captures/${encodeURIComponent(args.captureId)}/status`;
    try {
      const res = await this.callHmac(firmId, {
        method: "GET",
        url,
        toolName: "smarsh.get_capture_status",
      });
      const parsed = safeJson(res.bodyText) as SmarshCaptureStatus;
      this.audit({
        event: "smarsh.tool_audit",
        tool: "smarsh.get_capture_status",
        firm_id: firmId,
        outcome: "success",
        duration_ms: this.opts.clock.now() - startedAt,
        vendor_status_code: res.status,
        capture_id: args.captureId,
      });
      return parsed;
    } catch (err) {
      this.auditFailure(
        "smarsh.get_capture_status",
        firmId,
        startedAt,
        err,
        { capture_id: args.captureId },
      );
      throw err;
    }
  }

  // ---------------------------------------------------------------------------
  // Transport — wraps http.call with 401-retry for OAuth2; HMAC re-signs per call.
  // ---------------------------------------------------------------------------

  private async callBearer(
    firmId: string,
    req: {
      method: "GET" | "POST";
      url: string;
      body?: string;
      toolName: string;
    },
  ): Promise<{ bodyText: string; status: number }> {
    try {
      const headers = await this.bearerHeaders(firmId);
      const res = await this.opts.http.call({
        method: req.method,
        url: req.url,
        headers,
        ...(req.body !== undefined ? { body: req.body } : {}),
        toolName: req.toolName,
        firmId,
      });
      return { bodyText: res.bodyText, status: res.status };
    } catch (err) {
      if (
        err instanceof AdapterError &&
        err.code === "vendor_auth_failed" &&
        err.vendorStatusCode === 401
      ) {
        this.opts.logger.warn({
          event: "smarsh.auth_401_retry",
          tool_name: req.toolName,
          firm_id: firmId,
        });
        this.opts.oauthAuth?.invalidate(firmId);
        const retryHeaders = await this.bearerHeaders(firmId);
        const res = await this.opts.http.call({
          method: req.method,
          url: req.url,
          headers: retryHeaders,
          ...(req.body !== undefined ? { body: req.body } : {}),
          toolName: req.toolName,
          firmId,
        });
        return { bodyText: res.bodyText, status: res.status };
      }
      throw err;
    }
  }

  /**
   * HMAC has no refresh-cache to invalidate — we simply re-sign. But we DO retry once
   * on 401 with a fresh signature (in case of server-side clock drift that exceeded
   * the skew tolerance by the time the request arrived).
   */
  private async callHmac(
    firmId: string,
    req: {
      method: "GET" | "POST";
      url: string;
      body?: string;
      toolName: string;
    },
  ): Promise<{ bodyText: string; status: number }> {
    const body = req.body ?? "";
    try {
      const headers = await this.hmacHeaders(req.method, req.url, body);
      const res = await this.opts.http.call({
        method: req.method,
        url: req.url,
        headers,
        ...(req.body !== undefined ? { body: req.body } : {}),
        toolName: req.toolName,
        firmId,
      });
      return { bodyText: res.bodyText, status: res.status };
    } catch (err) {
      if (
        err instanceof AdapterError &&
        err.code === "vendor_auth_failed" &&
        err.vendorStatusCode === 401
      ) {
        this.opts.logger.warn({
          event: "smarsh.hmac_401_retry",
          tool_name: req.toolName,
          firm_id: firmId,
        });
        const retryHeaders = await this.hmacHeaders(req.method, req.url, body);
        const res = await this.opts.http.call({
          method: req.method,
          url: req.url,
          headers: retryHeaders,
          ...(req.body !== undefined ? { body: req.body } : {}),
          toolName: req.toolName,
          firmId,
        });
        return { bodyText: res.bodyText, status: res.status };
      }
      throw err;
    }
  }

  /** Common failure-audit emitter. Translates AdapterError → stable fields. */
  private auditFailure(
    tool: string,
    firmId: string,
    startedAt: number,
    err: unknown,
    ids: { message_id?: string; capture_id?: string; archive_id?: string },
  ): void {
    const adapterErr = err instanceof AdapterError ? err : null;
    this.audit({
      event: "smarsh.tool_audit",
      tool,
      firm_id: firmId,
      outcome: "failure",
      duration_ms: this.opts.clock.now() - startedAt,
      error_code: adapterErr?.code ?? "vendor_error",
      vendor_status_code: adapterErr?.vendorStatusCode ?? null,
      ...(ids.message_id ? { message_id: ids.message_id } : {}),
      ...(ids.capture_id ? { capture_id: ids.capture_id } : {}),
      ...(ids.archive_id ? { archive_id: ids.archive_id } : {}),
    });
  }

  // ---------------------------------------------------------------------------
  // Receipt-integrity verification (AC-SM8).
  // ---------------------------------------------------------------------------

  private verifyArchiveReceipt(
    receipt: SmarshArchiveReceipt,
    localContent: string,
    firmId: string,
  ): void {
    const localHash = sha256Hex(localContent);
    this.verifyHashAndSealedAt(
      "smarsh.archive_message",
      receipt.archive_id,
      receipt.content_hash,
      localHash,
      receipt.sealed_at,
      firmId,
    );
  }

  private verifyCaptureReceipt(
    receipt: SmarshCaptureReceipt,
    rawBytes: Uint8Array,
    firmId: string,
  ): void {
    const localHash = sha256Hex(rawBytes);
    this.verifyHashAndSealedAt(
      "smarsh.archive_capture",
      receipt.capture_id,
      receipt.content_hash,
      localHash,
      receipt.sealed_at,
      firmId,
    );
  }

  /** Shared hash + sealed_at skew check for archive + capture receipts. */
  private verifyHashAndSealedAt(
    tool: string,
    id: string | undefined,
    vendorHashRaw: unknown,
    localHash: string,
    sealedAtRaw: unknown,
    firmId: string,
  ): void {
    const vendorHash = stripSha256Prefix(vendorHashRaw);
    if (vendorHash === null || vendorHash !== localHash) {
      this.opts.logger.fatal({
        event: "smarsh.receipt_mismatch",
        severity: "CRITICAL",
        tool,
        firm_id: firmId,
        archive_id: id ?? "(missing)",
        reason: vendorHash === null ? "hash_prefix_invalid" : "hash_mismatch",
      });
      throw new AdapterError(
        "vendor_error",
        `Smarsh ${tool} receipt integrity verification failed (content_hash mismatch)`,
        null,
      );
    }
    if (typeof sealedAtRaw !== "string" || sealedAtRaw.length === 0) {
      this.opts.logger.fatal({
        event: "smarsh.receipt_mismatch",
        severity: "CRITICAL",
        tool,
        firm_id: firmId,
        archive_id: id ?? "(missing)",
        reason: "sealed_at_missing",
      });
      throw new AdapterError(
        "vendor_error",
        `Smarsh ${tool} receipt missing sealed_at`,
        null,
      );
    }
    const sealedMs = Date.parse(sealedAtRaw);
    if (!Number.isFinite(sealedMs)) {
      this.opts.logger.fatal({
        event: "smarsh.receipt_mismatch",
        severity: "CRITICAL",
        tool,
        firm_id: firmId,
        archive_id: id,
        reason: "sealed_at_unparseable",
      });
      throw new AdapterError(
        "vendor_error",
        `Smarsh ${tool} sealed_at is not ISO 8601`,
        null,
      );
    }
    const nowMs = this.opts.clock.now();
    const skewMs = Math.abs(nowMs - sealedMs);
    this.opts.logger.info({
      event: "smarsh.archive_sealed",
      tool,
      firm_id: firmId,
      archive_id: id,
      sealed_at_skew_ms: skewMs,
    });
    if (skewMs > SEALED_AT_SKEW_MS) {
      this.opts.logger.fatal({
        event: "smarsh.receipt_mismatch",
        severity: "CRITICAL",
        tool,
        firm_id: firmId,
        archive_id: id,
        reason: "sealed_at_skew_exceeded",
        skew_ms: skewMs,
      });
      throw new AdapterError(
        "vendor_error",
        `Smarsh ${tool} sealed_at skew ${skewMs}ms exceeds ±${SEALED_AT_SKEW_MS}ms tolerance`,
        null,
      );
    }
    if (skewMs > SEALED_AT_WARN_MS) {
      this.opts.logger.warn({
        event: "smarsh.sealed_at_skew_warn",
        tool,
        firm_id: firmId,
        archive_id: id,
        skew_ms: skewMs,
      });
    }
  }

  /** AC-SM8 C2 — verify retrieved content matches vendor-declared hash. */
  private verifyRetrievedHash(
    msg: SmarshRetrievedMessage,
    firmId: string,
  ): void {
    if (typeof msg.content !== "string") {
      this.opts.logger.fatal({
        event: "smarsh.receipt_mismatch",
        severity: "CRITICAL",
        firm_id: firmId,
        archive_id: msg.archive_id ?? "(missing)",
        reason: "content_missing",
      });
      throw new AdapterError(
        "vendor_error",
        "Smarsh retrieve response missing content",
        null,
      );
    }
    const localHash = sha256Hex(msg.content);
    const vendorHash = stripSha256Prefix(msg.content_hash);
    if (vendorHash === null || vendorHash !== localHash) {
      this.opts.logger.fatal({
        event: "smarsh.receipt_mismatch",
        severity: "CRITICAL",
        firm_id: firmId,
        archive_id: msg.archive_id ?? "(missing)",
        reason:
          vendorHash === null
            ? "hash_prefix_invalid"
            : "retrieved_hash_mismatch",
      });
      throw new AdapterError(
        "vendor_error",
        "Smarsh retrieved content hash does not match vendor content_hash (tamper suspected)",
        null,
      );
    }
  }
}
