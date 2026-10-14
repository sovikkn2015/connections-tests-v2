import type { AdapterConfig } from "@project-007/mcp-sdk";

export interface EMoneyConfig extends AdapterConfig {
  readonly vendor: "emoney";
  readonly rateLimitRpm: number;
  readonly rateLimitBurst: number;
  readonly apiBaseUrl: string;
  readonly requiredScope: string;
  readonly secretsBackend: "vault" | "aws" | "fake";
}

function parseIntEnv(name: string, env: NodeJS.ProcessEnv, dflt: number): number {
  const raw = env[name];
  if (!raw) return dflt;
  const n = parseInt(raw, 10);
  if (!Number.isFinite(n) || n <= 0) throw new Error(`env ${name} must be positive int`);
  return n;
}

function splitCsv(raw: string | undefined, dflt: readonly string[]): readonly string[] {
  if (!raw) return dflt;
  return Object.freeze(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): EMoneyConfig {
  const backend = (env.SECRETS_BACKEND ?? "").toLowerCase();
  if (!["vault", "aws", "fake"].includes(backend)) {
    throw new Error("SECRETS_BACKEND must be 'vault' or 'aws' (AC4.2)");
  }
  return {
    vendor: "emoney",
    adapterVersion: env.ADAPTER_VERSION ?? "0.1.0",
    vendorApiVersion: env.EMONEY_API_VERSION ?? "v2",
    port: parseIntEnv("ADAPTER_PORT", env, 8080),
    httpTimeoutMs: parseIntEnv("ADAPTER_HTTP_TIMEOUT_MS", env, 60_000),
    undiciConnections: parseIntEnv("ADAPTER_UNDICI_CONNECTIONS", env, 10),
    egressAllowlist: splitCsv(env.EMONEY_EGRESS_ALLOWLIST, [
      "api.emoneyadvisor.com",
      "api-sandbox.emoneyadvisor.com",
    ]),
    mtls: {
      clientCertPath: env.MTLS_CLIENT_CERT_PATH ?? "/etc/m11/mtls/tls.crt",
      clientKeyPath: env.MTLS_CLIENT_KEY_PATH ?? "/etc/m11/mtls/tls.key",
      caCertPath: env.MTLS_CA_CERT_PATH ?? "/etc/m11/mtls/ca.crt",
      trustedSubjectCn: env.MTLS_TRUSTED_SUBJECT_CN ?? "",
      enabled: env.MTLS_ENABLED !== "false",
    },
    firmIdRequired: true,
    rateLimitRpm: parseIntEnv("EMONEY_RATE_LIMIT_RPM", env, 1800),
    rateLimitBurst: parseIntEnv("EMONEY_RATE_LIMIT_BURST", env, 30),
    apiBaseUrl: env.EMONEY_API_BASE_URL ?? "https://api.emoneyadvisor.com",
    requiredScope: env.EMONEY_REQUIRED_SCOPE ?? "plan_summary:read",
    secretsBackend: backend as "vault" | "aws" | "fake",
  };
}

export const EMONEY_SECRET_PATHS = Object.freeze({
  oauthCredentials: "m11/emoney/oauth_credentials",
});

export const VENDOR_API_VERSION: string = "v2";
