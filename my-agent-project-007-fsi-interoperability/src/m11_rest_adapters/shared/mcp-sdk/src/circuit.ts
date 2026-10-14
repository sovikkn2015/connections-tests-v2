/**
 * Per-firm-per-vendor circuit breaker. Spec R6.
 *
 * Rules (AC6.1): OPEN after >=5 consecutive failures OR >50% failure rate over
 * rolling 60s window with >=10 calls. Reset after 30 000 ms.
 */

import type { Clock } from "./clock.js";
import { AdapterError } from "./errors.js";
import { LRUCache } from "./lru.js";

export type CircuitState = "CLOSED" | "OPEN" | "HALF_OPEN";

export interface CircuitBreakerConfig {
  readonly consecutiveFailureThreshold: number;
  readonly rollingWindowMs: number;
  readonly rollingMinCalls: number;
  readonly rollingFailureRate: number;
  readonly resetMs: number;
}

const DEFAULT_CFG: CircuitBreakerConfig = Object.freeze({
  consecutiveFailureThreshold: 5,
  rollingWindowMs: 60_000,
  rollingMinCalls: 10,
  rollingFailureRate: 0.5,
  resetMs: 30_000,
});

interface BreakerState {
  state: CircuitState;
  consecutiveFailures: number;
  recent: Array<{ at: number; ok: boolean }>;
  openedAt: number;
}

/** Single breaker keyed by `{firm_id}:{vendor}` (AC6.2). */
export class CircuitBreaker {
  private readonly states: LRUCache<string, BreakerState>;

  constructor(
    private readonly clock: Clock,
    private readonly cfg: CircuitBreakerConfig = DEFAULT_CFG,
    maxKeys: number = 1024,
  ) {
    this.states = new LRUCache({ max: maxKeys });
  }

  private get(key: string): BreakerState {
    let s = this.states.get(key);
    if (!s) {
      s = {
        state: "CLOSED",
        consecutiveFailures: 0,
        recent: [],
        openedAt: 0,
      };
      this.states.set(key, s);
    }
    return s;
  }

  state(key: string): CircuitState {
    const s = this.get(key);
    if (s.state === "OPEN") {
      if (this.clock.now() - s.openedAt >= this.cfg.resetMs) {
        s.state = "HALF_OPEN";
      }
    }
    return s.state;
  }

  /** Raise `vendor_circuit_open` if not callable. */
  assertCallable(key: string): void {
    const st = this.state(key);
    if (st === "OPEN") {
      throw new AdapterError(
        "vendor_circuit_open",
        `circuit breaker open for ${key}`,
        null,
      );
    }
  }

  recordSuccess(key: string): void {
    const s = this.get(key);
    const now = this.clock.now();
    s.consecutiveFailures = 0;
    s.recent.push({ at: now, ok: true });
    this.prune(s, now);
    if (s.state === "HALF_OPEN" || s.state === "OPEN") {
      s.state = "CLOSED";
      s.openedAt = 0;
    }
  }

  recordFailure(key: string): void {
    const s = this.get(key);
    const now = this.clock.now();
    s.consecutiveFailures += 1;
    s.recent.push({ at: now, ok: false });
    this.prune(s, now);

    if (s.consecutiveFailures >= this.cfg.consecutiveFailureThreshold) {
      s.state = "OPEN";
      s.openedAt = now;
      return;
    }
    if (s.recent.length >= this.cfg.rollingMinCalls) {
      const fails = s.recent.filter((c) => !c.ok).length;
      if (fails / s.recent.length > this.cfg.rollingFailureRate) {
        s.state = "OPEN";
        s.openedAt = now;
      }
    }
  }

  private prune(s: BreakerState, now: number): void {
    const horizon = now - this.cfg.rollingWindowMs;
    while (s.recent.length > 0 && s.recent[0]!.at < horizon) {
      s.recent.shift();
    }
  }

  /** Test helper. */
  reset(key: string): void {
    this.states.delete(key);
  }
}
