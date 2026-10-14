/**
 * Shared undici-backed HTTP client with:
 *  - Circuit breaker (R6)
 *  - Token-bucket rate limit (R5)
 *  - Exponential retry with ±25% jitter (AC6.4)
 *  - AC1.5 adapter timeout
 *  - AC5.7 Retry-After edge cases
 *  - Canonical error mapping (AC6.8)
 */

import { request, Agent, type Dispatcher } from "undici";

import type { Clock } from "./clock.js";
import { CircuitBreaker } from "./circuit.js";
import { AdapterError, type AdapterErrorCode } from "./errors.js";
import type { Logger } from "./logger.js";
import { RateLimiterRegistry, parseRetryAfter } from "./rate_limit.js";

export interface VendorCallOptions {
  readonly method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  readonly url: string;
  readonly headers?: Record<string, string>;
  readonly body?: string;
  readonly toolName: string;
  readonly firmId: string;
  /** Per-call override for max-retries. */
  readonly maxRetries?: number;
}

export interface VendorCallResult {
  readonly status: number;
  readonly headers: Record<string, string>;
  readonly bodyText: string;
  readonly retryCount: number;
}

export interface HttpClientConfig {
  readonly vendor: string;
  readonly httpTimeoutMs: number;
  readonly undiciConnections: number;
  readonly maxRetries: number;
  readonly baseBackoffMs: number;
}

const DEFAULT_CFG: Omit<HttpClientConfig, "vendor"> = {
  httpTimeoutMs: 60_000,
  undiciConnections: 10,
  maxRetries: 3,
  baseBackoffMs: 100,
};

/** Map vendor HTTP status to adapter error code (AC6.8 table). */
export function mapVendorStatusToErrorCode(status: number): AdapterErrorCode {
  if (status === 400) return "vendor_bad_request";
  if (status === 401) return "vendor_auth_failed";
  if (status === 403) return "vendor_forbidden";
  if (status === 404) return "vendor_not_found";
  if (status === 409) return "vendor_conflict";
  if (status === 412) return "vendor_conflict"; // SFDC ETag mismatch
  if (status === 422) return "vendor_unprocessable";
  if (status === 429) return "vendor_rate_limit";
  if (status >= 500) return "vendor_error";
  return "vendor_error";
}

export class VendorHttpClient {
  private readonly agent: Dispatcher;
  private readonly cfg: HttpClientConfig;

  constructor(
    cfg: Partial<HttpClientConfig> & { vendor: string },
    private readonly clock: Clock,
    private readonly logger: Logger,
    private readonly rateLimiter: RateLimiterRegistry,
    private readonly breaker: CircuitBreaker,
    agent?: Dispatcher,
  ) {
    this.cfg = { ...DEFAULT_CFG, ...cfg };
    this.agent =
      agent ??
      new Agent({
        connections: this.cfg.undiciConnections,
        pipelining: 0,
        keepAliveTimeout: 30_000,
        keepAliveMaxTimeout: 60_000,
      });
  }

  private timeoutSignal(): AbortSignal {
    return AbortSignal.timeout(this.cfg.httpTimeoutMs);
  }

  /** Per-attempt backoff in ms with ±25% jitter. */
  private backoffFor(attempt: number): number {
    const base = this.cfg.baseBackoffMs * Math.pow(2, attempt);
    const jitter = base * 0.25 * (Math.random() * 2 - 1);
    return Math.max(0, Math.round(base + jitter));
  }

  async call(opts: VendorCallOptions): Promise<VendorCallResult> {
    const key = `${opts.firmId}:${this.cfg.vendor}`;
    this.breaker.assertCallable(key);
    this.rateLimiter.assertAcquire(key);

    const maxRetries = opts.maxRetries ?? this.cfg.maxRetries;
    let lastErr: AdapterError | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const res = await request(opts.url, {
          method: opts.method,
          headers: opts.headers,
          body: opts.body,
          signal: this.timeoutSignal(),
          dispatcher: this.agent,
        });
        const headers: Record<string, string> = {};
        for (const [k, v] of Object.entries(res.headers)) {
          if (typeof v === "string") headers[k] = v;
          else if (Array.isArray(v)) headers[k] = v.join(",");
        }
        const bodyText = await res.body.text();
        const status = res.statusCode;

        if (status >= 200 && status < 300) {
          this.breaker.recordSuccess(key);
          return { status, headers, bodyText, retryCount: attempt };
        }

        if (status === 429) {
          const retry = parseRetryAfter(
            headers["retry-after"] ?? null,
            this.clock.now(),
          );
          const pauseMs = Math.max(retry.ms, 30_000);
          this.rateLimiter.pauseFor(key, pauseMs);
          this.breaker.recordFailure(key);
          this.logger.warn({
            event: "rate_limit_vendor_429",
            tool_name: opts.toolName,
            firm_id: opts.firmId,
            pause_ms: pauseMs,
            ...(retry.note ? { retry_after_note: retry.note } : {}),
          });
          throw new AdapterError(
            "vendor_rate_limit",
            `${this.cfg.vendor} returned 429; retry in ~${Math.ceil(pauseMs / 1000)}s`,
            429,
          );
        }

        // 4xx non-429 — not retryable.
        if (status >= 400 && status < 500) {
          this.breaker.recordFailure(key);
          const code = mapVendorStatusToErrorCode(status);
          throw new AdapterError(
            code,
            `${this.cfg.vendor} returned ${status}`,
            status,
          );
        }

        // 5xx — retryable.
        this.breaker.recordFailure(key);
        lastErr = new AdapterError(
          "vendor_error",
          `${this.cfg.vendor} returned ${status}`,
          status,
        );
      } catch (err) {
        if (err instanceof AdapterError) {
          if (err.code === "vendor_rate_limit") throw err;
          if (!err.retryable) throw err;
          lastErr = err;
        } else if (
          err instanceof Error &&
          (err.name === "AbortError" || err.name === "TimeoutError")
        ) {
          this.breaker.recordFailure(key);
          lastErr = new AdapterError(
            "vendor_timeout",
            `${this.cfg.vendor} timeout after ${this.cfg.httpTimeoutMs}ms`,
            null,
          );
        } else {
          this.breaker.recordFailure(key);
          lastErr = new AdapterError(
            "vendor_error",
            `${this.cfg.vendor} call failed: ${err instanceof Error ? err.message : String(err)}`,
            null,
          );
        }
      }

      if (attempt < maxRetries) {
        await this.clock.sleep(this.backoffFor(attempt));
      }
    }

    throw (
      lastErr ??
      new AdapterError(
        "vendor_error",
        `${this.cfg.vendor} retry exhausted`,
        null,
      )
    );
  }
}
