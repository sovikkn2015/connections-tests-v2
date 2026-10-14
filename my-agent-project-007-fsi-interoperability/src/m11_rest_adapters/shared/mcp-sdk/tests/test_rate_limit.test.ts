/**
 * Rate-limit + Retry-After edge-case tests. Spec R5 AC5.1 - AC5.9.
 */

import { describe, it, expect } from "vitest";

import { FakeClock } from "../src/clock.js";
import {
  DailyBucket,
  parseRetryAfter,
  RateLimiterRegistry,
  TokenBucket,
} from "../src/rate_limit.js";
import { AdapterError } from "../src/errors.js";

describe("TokenBucket — AC5.1, AC5.3, AC5.8", () => {
  it("allows burst then blocks", () => {
    const clk = new FakeClock(1_000_000);
    const tb = new TokenBucket({ rpm: 60, burst: 3 }, clk);
    expect(tb.tryAcquire().ok).toBe(true);
    expect(tb.tryAcquire().ok).toBe(true);
    expect(tb.tryAcquire().ok).toBe(true);
    const denied = tb.tryAcquire();
    expect(denied.ok).toBe(false);
    expect(denied.retryAfterMs).toBeGreaterThan(0);
  });

  it("refills after clock advances", () => {
    const clk = new FakeClock(1_000_000);
    const tb = new TokenBucket({ rpm: 60, burst: 1 }, clk);
    expect(tb.tryAcquire().ok).toBe(true);
    expect(tb.tryAcquire().ok).toBe(false);
    clk.advance(1100);
    expect(tb.tryAcquire().ok).toBe(true);
  });

  it("honours external pauseFor", () => {
    const clk = new FakeClock(1_000_000);
    const tb = new TokenBucket({ rpm: 60, burst: 10 }, clk);
    tb.pauseFor(5000);
    expect(tb.tryAcquire().ok).toBe(false);
    clk.advance(5001);
    expect(tb.tryAcquire().ok).toBe(true);
  });
});

describe("DailyBucket — AC5.2 SFDC 100K/24h", () => {
  it("resets at midnight UTC", () => {
    // Start at 23:59:00 UTC.
    const start = Date.UTC(2026, 4, 5, 23, 59, 0);
    const clk = new FakeClock(start);
    const db = new DailyBucket(3, clk);
    expect(db.tryAcquire().ok).toBe(true);
    expect(db.tryAcquire().ok).toBe(true);
    expect(db.tryAcquire().ok).toBe(true);
    expect(db.tryAcquire().ok).toBe(false);
    // Advance to next day 00:00:01.
    clk.setTime(Date.UTC(2026, 4, 6, 0, 0, 1));
    expect(db.tryAcquire().ok).toBe(true);
  });
});

describe("RateLimiterRegistry — AC5.4 per-firm", () => {
  it("isolates firms", () => {
    const clk = new FakeClock(0);
    const reg = new RateLimiterRegistry({ rpm: 60, burst: 1 }, clk);
    expect(reg.acquire("acme:sfdc").ok).toBe(true);
    // Acme exhausted.
    expect(reg.acquire("acme:sfdc").ok).toBe(false);
    // Bobco independent.
    expect(reg.acquire("bobco:sfdc").ok).toBe(true);
  });

  it("assertAcquire raises rate_limit_exceeded on empty", () => {
    const clk = new FakeClock(0);
    const reg = new RateLimiterRegistry({ rpm: 60, burst: 1 }, clk);
    reg.assertAcquire("acme:sfdc");
    expect(() => reg.assertAcquire("acme:sfdc")).toThrow(AdapterError);
    try {
      reg.assertAcquire("acme:sfdc");
    } catch (e) {
      expect((e as AdapterError).code).toBe("rate_limit_exceeded");
    }
  });

  it("AC5.9 concurrency burst — first 10 pass, rest 429", () => {
    const clk = new FakeClock(0);
    const reg = new RateLimiterRegistry({ rpm: 60, burst: 10 }, clk);
    let passed = 0;
    let denied = 0;
    for (let i = 0; i < 50; i++) {
      const r = reg.acquire("acme:sfdc");
      if (r.ok) passed++;
      else denied++;
    }
    expect(passed).toBe(10);
    expect(denied).toBe(40);
  });
});

describe("parseRetryAfter — AC5.7 five edge cases", () => {
  const now = 1_700_000_000_000;

  it("integer seconds path", () => {
    expect(parseRetryAfter("45", now).ms).toBe(45_000);
  });

  it("negative → 0, default 30", () => {
    const r = parseRetryAfter("-5", now);
    expect(r.ms).toBe(30_000);
    expect(r.note).toBe("negative_defaulted");
  });

  it("HTTP-date >300s in future → capped 300s", () => {
    const future = new Date(now + 3600_000).toUTCString();
    const r = parseRetryAfter(future, now);
    expect(r.ms).toBe(300_000);
    expect(r.note).toBe("retry_after_capped");
  });

  it("malformed → default 30s", () => {
    const r = parseRetryAfter("garbage!@#$", now);
    expect(r.ms).toBe(30_000);
    expect(r.note).toBe("retry_after_malformed");
  });

  it("absent → default 30s", () => {
    expect(parseRetryAfter(null, now).ms).toBe(30_000);
    expect(parseRetryAfter(undefined, now).ms).toBe(30_000);
    expect(parseRetryAfter("", now).ms).toBe(30_000);
  });

  it("zero → minimum 1s", () => {
    const r = parseRetryAfter("0", now);
    expect(r.ms).toBe(1_000);
    expect(r.note).toBe("zero_minimum");
  });

  it("seconds capped at 300 when > 300", () => {
    const r = parseRetryAfter("600", now);
    expect(r.ms).toBe(300_000);
    expect(r.note).toBe("retry_after_capped");
  });
});
