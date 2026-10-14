/**
 * Circuit breaker tests. Spec R6 AC6.1 - AC6.9.
 */

import { describe, it, expect } from "vitest";

import { CircuitBreaker } from "../src/circuit.js";
import { FakeClock } from "../src/clock.js";
import { AdapterError } from "../src/errors.js";

describe("CircuitBreaker — AC6.1 OPEN on 5 consecutive failures", () => {
  it("opens after 5 consecutive failures", () => {
    const clk = new FakeClock(0);
    const cb = new CircuitBreaker(clk);
    for (let i = 0; i < 4; i++) cb.recordFailure("acme:sfdc");
    expect(cb.state("acme:sfdc")).toBe("CLOSED");
    cb.recordFailure("acme:sfdc");
    expect(cb.state("acme:sfdc")).toBe("OPEN");
  });

  it("AC6.3 — assertCallable throws vendor_circuit_open when OPEN", () => {
    const clk = new FakeClock(0);
    const cb = new CircuitBreaker(clk);
    for (let i = 0; i < 5; i++) cb.recordFailure("acme:sfdc");
    expect(() => cb.assertCallable("acme:sfdc")).toThrow(AdapterError);
    try {
      cb.assertCallable("acme:sfdc");
    } catch (e) {
      expect((e as AdapterError).code).toBe("vendor_circuit_open");
    }
  });

  it("AC6.6 — success in CLOSED resets consecutive counter", () => {
    const clk = new FakeClock(0);
    const cb = new CircuitBreaker(clk);
    cb.recordFailure("acme:sfdc");
    cb.recordFailure("acme:sfdc");
    cb.recordSuccess("acme:sfdc");
    // 4 more fails should NOT open.
    for (let i = 0; i < 4; i++) cb.recordFailure("acme:sfdc");
    expect(cb.state("acme:sfdc")).toBe("CLOSED");
  });

  it("AC6.1 — OPEN on >50% failure rate with >=10 calls in 60s window", () => {
    const clk = new FakeClock(0);
    const cb = new CircuitBreaker(clk);
    // Alternate pass / fail, total 10 calls — 5 failures exactly = NOT >50%.
    // Need more than 50%, so use 6 fails + 4 succeeds.
    for (let i = 0; i < 4; i++) cb.recordSuccess("acme:sfdc");
    for (let i = 0; i < 4; i++) cb.recordFailure("acme:sfdc");
    // 4/8 = 50% — still closed.
    expect(cb.state("acme:sfdc")).toBe("CLOSED");
    cb.recordFailure("acme:sfdc");
    cb.recordFailure("acme:sfdc");
    // 6/10 = 60% — opens.
    expect(cb.state("acme:sfdc")).toBe("OPEN");
  });

  it("AC6.1 — transitions OPEN → HALF_OPEN after 30s reset", () => {
    const clk = new FakeClock(0);
    const cb = new CircuitBreaker(clk);
    for (let i = 0; i < 5; i++) cb.recordFailure("acme:sfdc");
    expect(cb.state("acme:sfdc")).toBe("OPEN");
    clk.advance(29_999);
    expect(cb.state("acme:sfdc")).toBe("OPEN");
    clk.advance(1);
    expect(cb.state("acme:sfdc")).toBe("HALF_OPEN");
  });

  it("AC6.2 — per-firm-per-vendor isolation", () => {
    const clk = new FakeClock(0);
    const cb = new CircuitBreaker(clk);
    for (let i = 0; i < 5; i++) cb.recordFailure("acme:sfdc");
    expect(cb.state("acme:sfdc")).toBe("OPEN");
    expect(cb.state("bobco:sfdc")).toBe("CLOSED");
    expect(cb.state("acme:orion")).toBe("CLOSED");
  });
});
