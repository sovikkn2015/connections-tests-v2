/**
 * Module-boundary + credential scans. Spec R4, R12, R14.
 *  - AC4.1 no hardcoded creds (regex scan)
 *  - AC7.3 no console.* usage
 *  - AC12.1 no imports from m{1..13}_* / compliance/ / @project-007/m{3,6,7}-*
 *  - AC12.4 no fs.* outside /etc/m11/mtls
 *  - AC12.6 no m7_schema_translators imports
 *  - AC14.4 no forbidden APIs: eval, Function(, vm.*, child_process, dgram, cluster, worker_threads, process.binding, process.dlopen
 */

import { describe, it, expect } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";

const SDK_SRC = path.resolve(__dirname, "../src");
const ADAPTERS_ROOT = path.resolve(__dirname, "../../..");

async function walk(dir: string, filter: (p: string) => boolean): Promise<string[]> {
  const out: string[] = [];
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (e.name === "node_modules" || e.name === "dist" || e.name === "tests") continue;
        out.push(...(await walk(full, filter)));
      } else if (filter(full)) {
        out.push(full);
      }
    }
  } catch {
    /* ignore missing dirs */
  }
  return out;
}

const SRC_FILTER = (p: string) => p.endsWith(".ts") && !p.endsWith(".test.ts");

describe("R4 AC4.1 — no hardcoded credentials", () => {
  const patterns: Array<[RegExp, string]> = [
    [/AKIA[0-9A-Z]{16}/, "AWS access key"],
    [/-----BEGIN (RSA |EC |OPENSSH |)?PRIVATE KEY-----/, "PEM private key"],
    [/sk_live_[A-Za-z0-9]{16,}/, "Stripe live key"],
    [/xox[pboa]-[A-Za-z0-9-]{10,}/, "Slack token"],
    [/eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}/, "JWT literal"],
    [/password\s*[:=]\s*["'][^"']{3,}["']/i, "hardcoded password"],
    [/api[_-]?key\s*[:=]\s*["'][A-Za-z0-9]{20,}["']/i, "hardcoded api_key"],
  ];

  it("scans all SDK .ts files", async () => {
    const files = await walk(SDK_SRC, SRC_FILTER);
    expect(files.length).toBeGreaterThan(0);
    for (const f of files) {
      const txt = await fs.readFile(f, "utf8");
      for (const [re, label] of patterns) {
        expect(
          re.test(txt),
          `${label} found in ${path.relative(ADAPTERS_ROOT, f)}`,
        ).toBe(false);
      }
    }
  });
});

describe("R7 AC7.3 — no console.*", () => {
  it("forbids console.log/info/warn/error in shared SDK src", async () => {
    const files = await walk(SDK_SRC, SRC_FILTER);
    for (const f of files) {
      const txt = await fs.readFile(f, "utf8");
      const stripped = txt.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
      expect(
        /\bconsole\.(log|info|warn|error|debug|trace)\s*\(/.test(stripped),
        `console.* call found in ${path.relative(ADAPTERS_ROOT, f)}`,
      ).toBe(false);
    }
  });
});

describe("R12 AC12.6 — no M7 import", () => {
  it("no reference to m7_schema_translators or @project-007/m7-* in SDK source", async () => {
    const files = await walk(SDK_SRC, SRC_FILTER);
    for (const f of files) {
      const txt = await fs.readFile(f, "utf8");
      expect(txt).not.toMatch(/m7_schema_translators/);
      expect(txt).not.toMatch(/@project-007\/m7-/);
    }
  });
});

describe("R12 AC12.1 — no cross-module imports", () => {
  it("no imports from m1..m13 / compliance", async () => {
    const files = await walk(SDK_SRC, SRC_FILTER);
    const bad =
      /from\s+["']@project-007\/(m(?!cp-sdk\b)[0-9a-z-]+|compliance-[0-9a-z-]+)["']|from\s+["'][^"']*m[0-9]+_[a-z_]+["']|from\s+["'][^"']*\/compliance\//;
    for (const f of files) {
      const txt = await fs.readFile(f, "utf8");
      expect(
        bad.test(txt),
        `bad import in ${path.relative(ADAPTERS_ROOT, f)}`,
      ).toBe(false);
    }
  });
});

describe("R14 AC14.4 — forbidden APIs", () => {
  it("no eval / Function(/ vm / child_process / dgram / cluster / worker_threads / process.binding", async () => {
    const files = await walk(SDK_SRC, SRC_FILTER);
    const forbidden: RegExp[] = [
      /\beval\s*\(/,
      /\bnew\s+Function\s*\(/,
      /from\s+["']node:vm["']/,
      /from\s+["']vm["']/,
      /from\s+["']node:child_process["']/,
      /from\s+["']child_process["']/,
      /from\s+["']node:dgram["']/,
      /from\s+["']dgram["']/,
      /from\s+["']node:cluster["']/,
      /from\s+["']cluster["']/,
      /from\s+["']node:worker_threads["']/,
      /from\s+["']worker_threads["']/,
      /process\.binding\s*\(/,
      /process\.dlopen\s*\(/,
    ];
    for (const f of files) {
      const txt = await fs.readFile(f, "utf8");
      for (const re of forbidden) {
        expect(re.test(txt), `${re} matched ${path.relative(ADAPTERS_ROOT, f)}`).toBe(false);
      }
    }
  });
});

describe("R12 AC12.4 — no general fs writes outside mtls dir", () => {
  it("no fs.writeFile / fs.createWriteStream / fs.appendFile calls in src", async () => {
    const files = await walk(SDK_SRC, SRC_FILTER);
    for (const f of files) {
      const txt = await fs.readFile(f, "utf8");
      expect(
        /\bfs\.(writeFile|writeFileSync|createWriteStream|appendFile|appendFileSync)\s*\(/.test(
          txt,
        ),
        `fs write in ${path.relative(ADAPTERS_ROOT, f)}`,
      ).toBe(false);
    }
  });
});
