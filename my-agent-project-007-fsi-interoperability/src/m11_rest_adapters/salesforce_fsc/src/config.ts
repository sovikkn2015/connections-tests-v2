/**
 * SFDC adapter config loader. Spec R4, R9, AC3.9, AC3.10, AC5.2, AC17.1.
 */

import type { AdapterConfig } from "@project-007/mcp-sdk";

export interface SfdcConfig extends AdapterConfig {
  readonly vendor: "salesforce_fsc";
  readonly rateLimitRpm: number;
  readonly rateLimitBurst: number;
  readonly dailyLimit: number;
  readonly secretsBackend: "vault" | "aws" | "fake";
}

function parseIntEnv(name: string, env: NodeJS.ProcessEnv, dflt: number): number {
  const raw = env[name];
  if (!raw) return dflt;
  const n = parseInt(raw, 10);
  if (!Number.isFinite(n) || n <= 0) {
    throw new Error(`env ${name} must be positive integer`);
  }
  return n;
}

function splitCsv(raw: string | undefined, dflt: readonly string[]): readonly string[] {
  if (!raw) return dflt;
  return Object.freeze(
    raw
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0),
  );
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): SfdcConfig {
  const adapterVersion = env.ADAPTER_VERSION ?? "0.1.0";
  const vendorApiVersion = env.SFDC_API_VERSION ?? "v59.0";
  const port = parseIntEnv("ADAPTER_PORT", env, 8080);
  const httpTimeoutMs = parseIntEnv("ADAPTER_HTTP_TIMEOUT_MS", env, 60_000);
  const undiciConnections = parseIntEnv("ADAPTER_UNDICI_CONNECTIONS", env, 10);
  if (undiciConnections < 1 || undiciConnections > 64) {
    throw new Error("ADAPTER_UNDICI_CONNECTIONS must be 1..64 (AC3.9)");
  }

  const backend = (env.SECRETS_BACKEND ?? "").toLowerCase();
  if (!["vault", "aws", "fake"].includes(backend)) {
    throw new Error("SECRETS_BACKEND must be 'vault' or 'aws' (AC4.2)");
  }

  return {
    vendor: "salesforce_fsc",
    adapterVersion,
    vendorApiVersion,
    port,
    httpTimeoutMs,
    undiciConnections,
    egressAllowlist: splitCsv(env.SFDC_EGRESS_ALLOWLIST, [
      "login.salesforce.com",
      "test.salesforce.com",
      "my.salesforce.com",
      "salesforce.com",
    ]),
    mtls: {
      clientCertPath: env.MTLS_CLIENT_CERT_PATH ?? "/etc/m11/mtls/tls.crt",
      clientKeyPath: env.MTLS_CLIENT_KEY_PATH ?? "/etc/m11/mtls/tls.key",
      caCertPath: env.MTLS_CA_CERT_PATH ?? "/etc/m11/mtls/ca.crt",
      trustedSubjectCn: env.MTLS_TRUSTED_SUBJECT_CN ?? "",
      enabled: env.MTLS_ENABLED !== "false",
    },
    firmIdRequired: true,
    rateLimitRpm: parseIntEnv("SFDC_RATE_LIMIT_RPM", env, 4166),
    rateLimitBurst: parseIntEnv("SFDC_RATE_LIMIT_BURST", env, 200),
    dailyLimit: parseIntEnv("SFDC_DAILY_LIMIT", env, 100_000),
    secretsBackend: backend as "vault" | "aws" | "fake",
  };
}

export const SFDC_SECRET_PATHS = Object.freeze({
  oauthCredentials: "m11/salesforce_fsc/oauth_credentials",
});

export const VENDOR_API_VERSION: string = "v59.0";
