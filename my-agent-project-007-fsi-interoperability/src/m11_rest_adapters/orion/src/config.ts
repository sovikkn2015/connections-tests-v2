/** Orion adapter config. Spec AC4.12 Phase 3 Basic-auth toggle. */

import type { AdapterConfig } from "@project-007/mcp-sdk";

export type OrionAuthMode = "oauth" | "basic";

export interface OrionConfig extends AdapterConfig {
  readonly vendor: "orion";
  readonly authMode: OrionAuthMode;
  readonly rateLimitRpm: number;
  readonly rateLimitBurst: number;
  readonly apiBaseUrl: string;
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
  return Object.freeze(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): OrionConfig {
  const mode = (env.ORION_AUTH_MODE ?? "oauth").toLowerCase();
  if (mode !== "oauth" && mode !== "basic") {
    throw new Error("ORION_AUTH_MODE must be 'oauth' or 'basic' (AC4.12)");
  }
  const backend = (env.SECRETS_BACKEND ?? "").toLowerCase();
  if (!["vault", "aws", "fake"].includes(backend)) {
    throw new Error("SECRETS_BACKEND must be 'vault' or 'aws' (AC4.2)");
  }
  return {
    vendor: "orion",
    adapterVersion: env.ADAPTER_VERSION ?? "0.1.0",
    vendorApiVersion: env.ORION_API_VERSION ?? "v2.0",
    port: parseIntEnv("ADAPTER_PORT", env, 8080),
    httpTimeoutMs: parseIntEnv("ADAPTER_HTTP_TIMEOUT_MS", env, 60_000),
    undiciConnections: parseIntEnv("ADAPTER_UNDICI_CONNECTIONS", env, 10),
    egressAllowlist: splitCsv(env.ORION_EGRESS_ALLOWLIST, [
      "api.orionadvisor.com",
      "stagingapi.orionadvisor.com",
    ]),
    mtls: {
      clientCertPath: env.MTLS_CLIENT_CERT_PATH ?? "/etc/m11/mtls/tls.crt",
      clientKeyPath: env.MTLS_CLIENT_KEY_PATH ?? "/etc/m11/mtls/tls.key",
      caCertPath: env.MTLS_CA_CERT_PATH ?? "/etc/m11/mtls/ca.crt",
      trustedSubjectCn: env.MTLS_TRUSTED_SUBJECT_CN ?? "",
      enabled: env.MTLS_ENABLED !== "false",
    },
    firmIdRequired: true,
    authMode: mode as OrionAuthMode,
    rateLimitRpm: parseIntEnv("ORION_RATE_LIMIT_RPM", env, 60),
    rateLimitBurst: parseIntEnv("ORION_RATE_LIMIT_BURST", env, 10),
    apiBaseUrl: env.ORION_API_BASE_URL ?? "https://api.orionadvisor.com",
    secretsBackend: backend as "vault" | "aws" | "fake",
  };
}

export const ORION_SECRET_PATHS = Object.freeze({
  oauthCredentials: "m11/orion/oauth_credentials",
  basicCredentials: "m11/orion/basic_credentials",
});

export const VENDOR_API_VERSION: string = "v2.0";
