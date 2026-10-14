/**
 * SSRF validation for vendor-returned URLs. Spec AC14.10 v0.2.0.
 *
 * Rules:
 *  - `https:` only (reject http/file/ftp/gopher/data).
 *  - Host must match egress FQDN allow-list (strict suffix / exact match).
 *  - Resolve to IP; reject RFC1918 / link-local / loopback / ULA / IPv4-mapped.
 *  - Reject bracketed IPv6 literals.
 */

import { promises as dns } from "node:dns";
import { isIP } from "node:net";

import { AdapterError } from "./errors.js";

export interface SsrfOptions {
  /** Optional DNS resolver — allows injection for tests. */
  readonly resolve?: (host: string) => Promise<string[]>;
}

/** Allow-list match: exact host OR host ends with `.{entry}`. */
export function hostMatchesAllowlist(
  host: string,
  allowlist: readonly string[],
): boolean {
  const h = host.toLowerCase();
  for (const raw of allowlist) {
    const entry = raw.toLowerCase().replace(/^\*\./, "");
    if (h === entry || h.endsWith("." + entry)) return true;
  }
  return false;
}

/** Classify IPv4 address into private / link-local / loopback / public. */
export function classifyIPv4(
  ip: string,
): "rfc1918" | "link_local" | "loopback" | "multicast" | "broadcast" | "public" {
  const parts = ip.split(".").map(Number);
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n) || n < 0 || n > 255)) {
    return "public";
  }
  const a = parts[0]!;
  const b = parts[1]!;
  if (a === 127) return "loopback";
  if (a === 169 && b === 254) return "link_local";
  if (a === 10) return "rfc1918";
  if (a === 172 && b >= 16 && b <= 31) return "rfc1918";
  if (a === 192 && b === 168) return "rfc1918";
  if (a >= 224 && a <= 239) return "multicast";
  if (a === 255) return "broadcast";
  return "public";
}

/** Classify IPv6 address. */
export function classifyIPv6(
  ip: string,
): "loopback" | "link_local" | "ula" | "ipv4_mapped" | "public" {
  const lower = ip.toLowerCase();
  if (lower === "::1") return "loopback";
  if (lower.startsWith("fe80:") || lower.startsWith("fe80::")) return "link_local";
  // fc00::/7 — unique local address (fc or fd first byte).
  if (lower.startsWith("fc") || lower.startsWith("fd")) return "ula";
  if (lower.startsWith("::ffff:") || lower.startsWith("::")) return "ipv4_mapped";
  return "public";
}

export interface SsrfResult {
  readonly ok: true;
  readonly resolvedIp: string;
  readonly classification: string;
}

export interface SsrfFailure {
  readonly ok: false;
  readonly reason: string;
  readonly hostOrIp: string;
  readonly classification?: string;
}

/**
 * Validate a vendor-returned URL against SSRF risk.
 * Returns structured result; throws on malformed URL to fail fast.
 */
export async function validateVendorURL(
  urlString: string,
  allowlist: readonly string[],
  opts: SsrfOptions = {},
): Promise<SsrfResult | SsrfFailure> {
  let parsed: URL;
  try {
    parsed = new URL(urlString);
  } catch {
    return { ok: false, reason: "malformed_url", hostOrIp: "" };
  }

  if (parsed.protocol !== "https:") {
    return { ok: false, reason: "non_https", hostOrIp: parsed.host };
  }

  const hostname = parsed.hostname;
  const ipVersion = isIP(hostname);
  if (ipVersion !== 0) {
    // Caller supplied raw IP literal — always reject.
    const cls =
      ipVersion === 4 ? classifyIPv4(hostname) : classifyIPv6(hostname);
    return {
      ok: false,
      reason: `ip_literal_${cls}`,
      hostOrIp: hostname,
      classification: cls,
    };
  }

  if (!hostMatchesAllowlist(hostname, allowlist)) {
    return { ok: false, reason: "host_not_allowlisted", hostOrIp: hostname };
  }

  const resolver =
    opts.resolve ??
    (async (h: string): Promise<string[]> => {
      const res = await dns.lookup(h, { all: true, verbatim: true });
      return res.map((r) => r.address);
    });

  let addrs: string[];
  try {
    addrs = await resolver(hostname);
  } catch {
    return { ok: false, reason: "dns_resolve_failed", hostOrIp: hostname };
  }
  if (addrs.length === 0) {
    return { ok: false, reason: "dns_no_records", hostOrIp: hostname };
  }

  for (const addr of addrs) {
    const v = isIP(addr);
    const cls = v === 4 ? classifyIPv4(addr) : classifyIPv6(addr);
    if (cls !== "public") {
      return {
        ok: false,
        reason: `resolved_${cls}`,
        hostOrIp: addr,
        classification: cls,
      };
    }
  }

  return { ok: true, resolvedIp: addrs[0]!, classification: "public" };
}

/** Throwing variant — raises AdapterError `vendor_ssrf_blocked` on failure. */
export async function assertVendorURLSafe(
  url: string,
  allowlist: readonly string[],
  opts: SsrfOptions = {},
): Promise<string> {
  const res = await validateVendorURL(url, allowlist, opts);
  if (!res.ok) {
    throw new AdapterError(
      "vendor_ssrf_blocked",
      `vendor URL blocked by SSRF check (${res.reason})`,
      null,
    );
  }
  return res.resolvedIp;
}
