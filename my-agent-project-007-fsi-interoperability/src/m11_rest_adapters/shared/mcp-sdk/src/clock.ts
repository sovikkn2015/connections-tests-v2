/**
 * Clock abstraction — DI-testable. Spec AC5.1, AC16.4.
 */

export interface Clock {
  now(): number;
  sleep(ms: number): Promise<void>;
}

export class SystemClock implements Clock {
  now(): number {
    return Date.now();
  }
  sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

/** FakeClock — deterministic. Only `advance()` moves time forward. */
export class FakeClock implements Clock {
  private t: number;
  private readonly waiters: Array<{ due: number; resolve: () => void }> = [];

  constructor(startMs: number = 0) {
    this.t = startMs;
  }

  now(): number {
    return this.t;
  }

  sleep(ms: number): Promise<void> {
    return new Promise<void>((resolve) => {
      this.waiters.push({ due: this.t + ms, resolve });
    });
  }

  advance(ms: number): void {
    this.t += ms;
    for (let i = this.waiters.length - 1; i >= 0; i--) {
      const w = this.waiters[i]!;
      if (w.due <= this.t) {
        w.resolve();
        this.waiters.splice(i, 1);
      }
    }
  }

  setTime(ms: number): void {
    if (ms < this.t) {
      throw new Error("FakeClock cannot go backward");
    }
    this.advance(ms - this.t);
  }
}
