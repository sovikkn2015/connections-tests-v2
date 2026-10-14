/**
 * SSRF validation tests. Spec AC14.10 v0.2.0.
 *
 * Covers: non-https, disallowed host, IP literal, private IPv4/IPv6,
 * link-local, loopback, ULA, and the acceptance path.
 */

import { describe, it, expect } from "vitest";

import {
  assertVendorURLSafe,
  classifyIPv4,
  classifyIPv6,
  hostMatchesAllowlist,
  validateVendorURL,
} from "../src/ssrf.js";
import { AdapterError } from "../src/errors.js";

const ALLOW = Object.freeze([
  "my.salesforce.com",
  "salesforce.com",
  "api.orionadvisor.com",
]);

describe("hostMatchesAllowlist", () => {
  it("matches exact", () => {
    expect(hostMatchesAllowlist("salesforce.com", ALLOW)).toBe(true);
  });
  it("matches subdomain", () => {
    expect(hostMatchesAllowlist("acme.my.salesforce.com", ALLOW)).toBe(true);
  });
  it("rejects unrelated host", () => {
    expect(hostMatchesAllowlist("evil.example.com", ALLOW)).toBe(false);
  });
  it("rejects partial suffix collision", () => {
    expect(hostMatchesAllowlist("notsalesforce.com", ALLOW)).toBe(false);
  });
});

describe("classifyIPv4", () => {
  it("detects RFC1918 10/8, 172.16/12, 192.168/16", () => {
    expect(classifyIPv4("10.0.0.1")).toBe("rfc1918");
    expect(classifyIPv4("172.16.0.1")).toBe("rfc1918");
    expect(classifyIPv4("172.31.255.255")).toBe("rfc1918");
    expect(classifyIPv4("192.168.1.1")).toBe("rfc1918");
  });
  it("detects link-local 169.254/16", () => {
    expect(classifyIPv4("169.254.169.254")).toBe("link_local");
  });
  it("detects loopback 127/8", () => {
    expect(classifyIPv4("127.0.0.1")).toBe("loopback");
  });
  it("accepts public IP", () => {
    expect(classifyIPv4("52.84.100.50")).toBe("public");
  });
  it("172.15 is NOT RFC1918", () => {
    expect(classifyIPv4("172.15.0.1")).toBe("public");
  });
});

describe("classifyIPv6", () => {
  it("detects loopback ::1", () => {
    expect(classifyIPv6("::1")).toBe("loopback");
  });
  it("detects link-local fe80::", () => {
    expect(classifyIPv6("fe80::1")).toBe("link_local");
  });
  it("detects ULA fc00::/7", () => {
    expect(classifyIPv6("fc00::1")).toBe("ula");
    expect(classifyIPv6("fd12:3456::1")).toBe("ula");
  });
});

describe("validateVendorURL", () => {
  const fakeDns = (ip: string) => async (_h: string) => [ip];

  it("rejects non-https", async () => {
    const r = await validateVendorURL(
      "http://acme.my.salesforce.com/data",
      ALLOW,
      { resolve: fakeDns("52.1.1.1") },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe("non_https");
  });

  it("rejects disallowed host", async () => {
    const r = await validateVendorURL(
      "https://evil.example.com/a",
      ALLOW,
      { resolve: fakeDns("52.1.1.1") },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe("host_not_allowlisted");
  });

  it("rejects IP-literal URL even if it maps to a public address", async () => {
    const r = await validateVendorURL("https://52.1.1.1/", ALLOW);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toMatch(/ip_literal/);
  });

  it("rejects link-local 169.254.169.254 (AWS EC2 metadata)", async () => {
    const r = await validateVendorURL(
      "https://acme.my.salesforce.com/",
      ALLOW,
      { resolve: fakeDns("169.254.169.254") },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe("resolved_link_local");
  });

  it("rejects RFC1918 resolution", async () => {
    const r = await validateVendorURL(
      "https://acme.my.salesforce.com/",
      ALLOW,
      { resolve: fakeDns("10.0.0.5") },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe("resolved_rfc1918");
  });

  it("accepts allow-listed host with public resolved IP", async () => {
    const r = await validateVendorURL(
      "https://acme.my.salesforce.com/services/data",
      ALLOW,
      { resolve: fakeDns("52.84.100.50") },
    );
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.classification).toBe("public");
  });

  it("rejects malformed URL", async () => {
    const r = await validateVendorURL("::::", ALLOW);
    expect(r.ok).toBe(false);
  });
});

describe("assertVendorURLSafe", () => {
  it("throws AdapterError vendor_ssrf_blocked on reject", async () => {
    await expect(
      assertVendorURLSafe(
        "http://acme.my.salesforce.com/",
        ALLOW,
      ),
    ).rejects.toThrow(AdapterError);
    try {
      await assertVendorURLSafe(
        "http://acme.my.salesforce.com/",
        ALLOW,
      );
    } catch (e) {
      expect((e as AdapterError).code).toBe("vendor_ssrf_blocked");
    }
  });

  it("returns resolved IP on accept", async () => {
    const ip = await assertVendorURLSafe(
      "https://acme.my.salesforce.com/",
      ALLOW,
      { resolve: async () => ["52.1.1.1"] },
    );
    expect(ip).toBe("52.1.1.1");
  });
});
