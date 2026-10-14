/** Smarsh adapter config — env parsing only. Credentials live in Vault. */

import type { AdapterConfig } from "@project-007/mcp-sdk";

export type SmarshAuthMode = "oauth2" | "hmac";

export interface SmarshConfig extends AdapterConfig {
  readonly vendor: "smarsh";
  readonly rateLimitRpm: number;
  readonly rateLimitBurst: number;
  readonly apiBaseUrl: string;
  readonly oauthTokenUrl: string;
  readonly secretsBackend: "vault" | "aws" | "fake";
  readonly authMode: SmarshAuthMode;
  /** Vault paths (NEVER raw creds) — Steering Rule 20. */
  readonly secretPaths: {
    readonly oauthCredentials: string;
    readonly apiKey: string;
    readonly hmacSecret: string;
  };
  /** HMAC replay-defence skew tolerance (seconds). */
  readonly hmacClockSkewSec: number;
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

function splitCsv(
  raw: string | undefined,
  dflt: readonly string[],
): readonly string[] {
  if (!raw) return dflt;
  return Object.freeze(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

function parseAuthMode(raw: string | undefined): SmarshAuthMode {
  const v = (raw ?? "oauth2").toLowerCase();
  if (v !== "oauth2" && v !== "hmac") {
    throw new Error(
      `SMARSH_AUTH_MODE must be 'oauth2' or 'hmac' (got '${raw}')`,
    );
  }
  return v;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): SmarshConfig {
  const backend = (env.SECRETS_BACKEND ?? "").toLowerCase();
  if (!["vault", "aws", "fake"].includes(backend)) {
    throw new Error("SECRETS_BACKEND must be 'vault' or 'aws' (Rule 20)");
  }
  return {
    vendor: "smarsh",
    adapterVersion: env.ADAPTER_VERSION ?? "0.1.0",
    vendorApiVersion: env.SMARSH_API_VERSION ?? "v1",
    port: parseIntEnv("ADAPTER_PORT", env, 8080),
    httpTimeoutMs: parseIntEnv("ADAPTER_HTTP_TIMEOUT_MS", env, 60_000),
    undiciConnections: parseIntEnv("ADAPTER_UNDICI_CONNECTIONS", env, 10),
    egressAllowlist: splitCsv(env.SMARSH_EGRESS_ALLOWLIST, [
      "api.smarsh.com",
      "auth.smarsh.com",
    ]),
    mtls: {
      clientCertPath: env.MTLS_CLIENT_CERT_PATH ?? "/etc/m11/mtls/tls.crt",
      clientKeyPath: env.MTLS_CLIENT_KEY_PATH ?? "/etc/m11/mtls/tls.key",
      caCertPath: env.MTLS_CA_CERT_PATH ?? "/etc/m11/mtls/ca.crt",
      trustedSubjectCn: env.MTLS_TRUSTED_SUBJECT_CN ?? "",
      enabled: env.MTLS_ENABLED !== "false",
    },
    firmIdRequired: true,
    rateLimitRpm: parseIntEnv("SMARSH_RATE_LIMIT_RPM", env, 300),
    rateLimitBurst: parseIntEnv("SMARSH_RATE_LIMIT_BURST", env, 50),
    apiBaseUrl: env.SMARSH_API_BASE_URL ?? "https://api.smarsh.com",
    oauthTokenUrl: env.SMARSH_OAUTH_URL ?? "https://auth.smarsh.com/oauth/token",
    secretsBackend: backend as "vault" | "aws" | "fake",
    authMode: parseAuthMode(env.SMARSH_AUTH_MODE),
    secretPaths: {
      oauthCredentials:
        env.SMARSH_OAUTH_CREDENTIALS_VAULT_PATH ?? "m11/smarsh/oauth_credentials",
      apiKey: env.SMARSH_API_KEY_VAULT_PATH ?? "m11/smarsh/api_key",
      hmacSecret: env.SMARSH_HMAC_SECRET_VAULT_PATH ?? "m11/smarsh/hmac_secret",
    },
    hmacClockSkewSec: parseIntEnv("SMARSH_HMAC_CLOCK_SKEW_SEC", env, 300),
  };
}

/**
 * Deprecated legacy export — kept for import-compat with existing callsites.
 * New code should use `config.secretPaths.*` which is env-driven.
 */
export const SMARSH_SECRET_PATHS = Object.freeze({
  oauthCredentials: "m11/smarsh/oauth_credentials",
  apiKey: "m11/smarsh/api_key",
  hmacSecret: "m11/smarsh/hmac_secret",
});

/** Exact-match OAuth scopes required — spec §7 + AC-SM5. */
export const REQUIRED_SCOPES: ReadonlySet<string> = Object.freeze(
  new Set(["archive.write", "archive.read", "archive.search"]),
) as ReadonlySet<string>;

export const VENDOR_API_VERSION: string = "v1";
