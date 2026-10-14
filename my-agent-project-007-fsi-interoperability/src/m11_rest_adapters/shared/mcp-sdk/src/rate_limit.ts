/**
 * Token bucket + daily bucket rate limiters. Spec R5.
 *
 * Per-firm-per-vendor key via LRU. Fail-closed — empty bucket → 429.
 */

import type { Clock } from "./clock.js";
import { AdapterError } from "./errors.js";
import { LRUCache } from "./lru.js";

export interface BucketConfig {
  readonly rpm: number;
  readonly burst: number;
}

export interface AcquireResult {
  readonly ok: boolean;
  readonly retryAfterMs: number;
}

/** Classic token bucket; refills `rpm/60000` tokens per ms up to `burst`. */
export class TokenBucket {
  private tokens: number;
  private lastRefill: number;
  private pausedUntil: number = 0;

  constructor(
    private readonly cfg: BucketConfig,
    private readonly clock: Clock,
  ) {
    this.tokens = cfg.burst;
    this.lastRefill = clock.now();
  }

  private refill(now: number): void {
    const elapsed = now - this.lastRefill;
    if (elapsed <= 0) return;
    const rate = this.cfg.rpm / 60_000; // tokens per ms
    this.tokens = Math.min(this.cfg.burst, this.tokens + elapsed * rate);
    this.lastRefill = now;
  }

  /** Attempt to acquire 1 token. */
  tryAcquire(): AcquireResult {
    const now = this.clock.now();
    if (now < this.pausedUntil) {
      return { ok: false, retryAfterMs: this.pausedUntil - now };
    }
    this.refill(now);
    if (this.tokens >= 1) {
      this.tokens -= 1;
      return { ok: true, retryAfterMs: 0 };
    }
    const needed = 1 - this.tokens;
    const rate = this.cfg.rpm / 60_000;
    return { ok: false, retryAfterMs: Math.ceil(needed / rate) };
  }

  /** Externally pause for N ms (e.g. vendor 429 Retry-After). */
  pauseFor(ms: number): void {
    const now = this.clock.now();
    const until = now + ms;
    if (until > this.pausedUntil) this.pausedUntil = until;
  }

  /** Test hook. */
  snapshot(): { tokens: number; pausedUntil: number } {
    return { tokens: this.tokens, pausedUntil: this.pausedUntil };
  }
}

/** SFDC-style daily budget — 100K/24h, resets midnight UTC (AC5.2). */
export class DailyBucket {
  private remaining: number;
  private resetAt: number;

  constructor(
    private readonly dailyLimit: number,
    private readonly clock: Clock,
  ) {
    this.remaining = dailyLimit;
    this.resetAt = this.nextMidnightUtc(clock.now());
  }

  private nextMidnightUtc(now: number): number {
    const d = new Date(now);
    return Date.UTC(
      d.getUTCFullYear(),
      d.getUTCMonth(),
      d.getUTCDate() + 1,
      0,
      0,
      0,
      0,
    );
  }

  private rollIfNeeded(now: number): void {
    if (now >= this.resetAt) {
      this.remaining = this.dailyLimit;
      this.resetAt = this.nextMidnightUtc(now);
    }
  }

  tryAcquire(): AcquireResult {
    const now = this.clock.now();
    this.rollIfNeeded(now);
    if (this.remaining <= 0) {
      return { ok: false, retryAfterMs: this.resetAt - now };
    }
    this.remaining -= 1;
    return { ok: true, retryAfterMs: 0 };
  }

  snapshot(): { remaining: number; resetAt: number } {
    return { remaining: this.remaining, resetAt: this.resetAt };
  }
}

/** Per-firm-per-vendor registry of TokenBuckets (AC5.4 LRU 1024). */
export class RateLimiterRegistry {
  private readonly buckets: LRUCache<string, TokenBucket>;
  private readonly daily: LRUCache<string, DailyBucket> | null;

  constructor(
    private readonly bucketCfg: BucketConfig,
    private readonly clock: Clock,
    private readonly dailyLimit: number | null = null,
    maxKeys: number = 1024,
  ) {
    this.buckets = new LRUCache({ max: maxKeys });
    this.daily = dailyLimit
      ? new LRUCache<string, DailyBucket>({ max: maxKeys })
      : null;
  }

  private getBucket(key: string): TokenBucket {
    let b = this.buckets.get(key);
    if (!b) {
      b = new TokenBucket(this.bucketCfg, this.clock);
      this.buckets.set(key, b);
    }
    return b;
  }

  private getDaily(key: string): DailyBucket | null {
    if (!this.daily || this.dailyLimit === null) return null;
    let d = this.daily.get(key);
    if (!d) {
      d = new DailyBucket(this.dailyLimit, this.clock);
      this.daily.set(key, d);
    }
    return d;
  }

  acquire(key: string): AcquireResult {
    const b = this.getBucket(key);
    const d = this.getDaily(key);
    if (d) {
      const dr = d.tryAcquire();
      if (!dr.ok) return dr;
    }
    return b.tryAcquire();
  }

  pauseFor(key: string, ms: number): void {
    this.getBucket(key).pauseFor(ms);
  }

  /** Assert — raise `rate_limit_exceeded` on empty. */
  assertAcquire(key: string): void {
    const r = this.acquire(key);
    if (!r.ok) {
      throw new AdapterError(
        "rate_limit_exceeded",
        `local rate limit exhausted; retry in ~${Math.ceil(r.retryAfterMs / 1000)}s`,
        null,
      );
    }
  }
}

/**
 * Parse vendor Retry-After header per AC5.7. All five edge cases covered.
 * Returns milliseconds.
 */
export function parseRetryAfter(
  raw: string | null | undefined,
  nowMs: number,
): { ms: number; note?: string } {
  if (raw === null || raw === undefined || raw === "") {
    return { ms: 30_000, note: "absent" };
  }
  const trimmed = raw.trim();

  // Integer seconds path.
  if (/^-?\d+$/.test(trimmed)) {
    const secs = parseInt(trimmed, 10);
    if (secs < 0) return { ms: 30_000, note: "negative_defaulted" };
    if (secs === 0) return { ms: 1_000, note: "zero_minimum" };
    const cappedSecs = Math.min(secs, 300);
    return {
      ms: cappedSecs * 1000,
      ...(cappedSecs < secs ? { note: "retry_after_capped" } : {}),
    };
  }

  // HTTP-date path.
  const parsed = Date.parse(trimmed);
  if (!Number.isNaN(parsed)) {
    const deltaMs = parsed - nowMs;
    if (deltaMs <= 0) return { ms: 30_000, note: "http_date_past" };
    const capped = Math.min(deltaMs, 300_000);
    return {
      ms: capped,
      ...(capped < deltaMs ? { note: "retry_after_capped" } : {}),
    };
  }

  return { ms: 30_000, note: "retry_after_malformed" };
}
