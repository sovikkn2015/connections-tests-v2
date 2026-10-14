/**
 * Smarsh Connected Archive HMAC-SHA256 request signer.
 *
 * Spec §7.2 + AC-SM5b.
 *
 * Connected Archive auth scheme (distinct from Professional Archive OAuth2):
 *
 *   Headers:
 *     X-Smarsh-API-Key:    {apiKey}
 *     X-Smarsh-Timestamp:  {unix-seconds}
 *     X-Smarsh-Signature:  hex(hmac_sha256(secret, signingString))
 *
 *   signingString = METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + sha256hex(body)
 *
 *   The timestamp → replay-defence: receiver rejects > ±SMARSH_HMAC_CLOCK_SKEW_SEC
 *   (default 300 s). We embed the timestamp locally to log skew and fail fast if the
 *   adapter's clock is wrong.
 *
 *   The body hash is the SHA-256 of the EXACT serialized UTF-8 body bytes the client
 *   will send (empty string "" for GET). Callers must sign the same bytes they send —
 *   no re-serialization.
 *
 * Steering Rule 20: apiKey + hmacSecret are loaded by path at call time. No disk caching
 * beyond SecretsClient's own refresh policy.
 *
 * Rule 4 (M6): this module does not talk to M6. It only produces headers.
 */

import { createHash, createHmac } from "node:crypto";
import { timingSafeEqual } from "node:crypto";

import {
  AdapterError,
  type Clock,
  type Logger,
  type SecretsClient,
} from "@project-007/mcp-sdk";

export interface SmarshHmacOptions {
  readonly secrets: SecretsClient;
  readonly apiKeyPath: string;
  readonly hmacSecretPath: string;
  readonly clock: Clock;
  readonly logger: Logger;
}

export interface HmacSignedHeaders {
  readonly "x-smarsh-api-key": string;
  readonly "x-smarsh-timestamp": string;
  readonly "x-smarsh-signature": string;
  readonly "x-smarsh-body-sha256": string;
}

/** Canonical signing string (public for unit tests + parity verification). */
export function buildSigningString(
  method: string,
  path: string,
  timestampSec: number,
  body: string,
): string {
  const methodUc = method.toUpperCase();
  const bodyHash = createHash("sha256").update(body, "utf8").digest("hex");
  return `${methodUc}\n${path}\n${timestampSec}\n${bodyHash}`;
}

/** Hex-encode HMAC-SHA256(secret, signingString). */
export function computeHmacSignature(secret: string, signingString: string): string {
  return createHmac("sha256", secret).update(signingString, "utf8").digest("hex");
}

/**
 * Constant-time hex comparison — used by tests / receipt-verify paths where the
 * adapter validates a signature returned by Smarsh (e.g. webhook ACKs, future use).
 * Node's `Buffer.compare` is variable-time so we use `timingSafeEqual`.
 *
 * Strings that are not valid lowercase hex are rejected without decoding — both
 * to prevent `Buffer.from("not-hex", "hex")` silently returning an empty buffer
 * AND to preserve constant-time behaviour for the known-valid case.
 */
export function constantTimeHexEqual(a: string, b: string): boolean {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  if (a.length === 0) return true;
  if (a.length % 2 !== 0) return false;
  // Both must be valid hex (lowercase or uppercase).
  if (!/^[0-9a-fA-F]+$/.test(a) || !/^[0-9a-fA-F]+$/.test(b)) return false;
  try {
    return timingSafeEqual(Buffer.from(a, "hex"), Buffer.from(b, "hex"));
  } catch {
    return false;
  }
}

interface HmacSecretsBlob {
  readonly apiKey: string;
  readonly hmacSecret: string;
}

export class SmarshHmacSigner {
  private bootstrappedOnce = false;

  constructor(private readonly opts: SmarshHmacOptions) {}

  healthy(): boolean {
    return this.bootstrappedOnce;
  }

  /**
   * Load the api-key and hmac-secret from Vault at call-time. SecretsClient implements
   * its own LRU/TTL, so this is fast on hot paths. We do NOT keep a plaintext copy.
   */
  private async loadSecrets(): Promise<HmacSecretsBlob> {
    // Both Vault paths MUST be strings of reasonable length. Validate shape to catch
    // misconfiguration early (Rule 32 — validate inputs).
    const apiKey = await this.opts.secrets.getSecret(this.opts.apiKeyPath);
    const hmacSecret = await this.opts.secrets.getSecret(this.opts.hmacSecretPath);
    if (!apiKey || typeof apiKey !== "string" || apiKey.length < 8) {
      throw new AdapterError(
        "vendor_auth_failed",
        "Smarsh api_key missing or too short",
        null,
      );
    }
    if (!hmacSecret || typeof hmacSecret !== "string" || hmacSecret.length < 32) {
      throw new AdapterError(
        "vendor_auth_failed",
        "Smarsh hmac_secret missing or too short (<32 bytes)",
        null,
      );
    }
    return { apiKey, hmacSecret };
  }

  /**
   * Sign a request. Returns the complete HMAC headers block to merge with the
   * caller's base headers. The `path` MUST be the URL path including leading `/`
   * but NOT the scheme+host (matches §7.2 signing-string contract).
   */
  async sign(args: {
    readonly method: string;
    readonly path: string;
    readonly body: string;
  }): Promise<HmacSignedHeaders> {
    const { apiKey, hmacSecret } = await this.loadSecrets();
    const nowMs = this.opts.clock.now();
    const timestampSec = Math.floor(nowMs / 1000);
    const signingString = buildSigningString(
      args.method,
      args.path,
      timestampSec,
      args.body,
    );
    const signature = computeHmacSignature(hmacSecret, signingString);
    const bodySha = createHash("sha256").update(args.body, "utf8").digest("hex");
    this.bootstrappedOnce = true;

    return Object.freeze({
      "x-smarsh-api-key": apiKey,
      "x-smarsh-timestamp": String(timestampSec),
      "x-smarsh-signature": signature,
      "x-smarsh-body-sha256": bodySha,
    });
  }
}
