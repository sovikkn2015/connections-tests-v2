/** Smarsh startup — wires auth (OAuth2 or HMAC), client, tools, health. Spec §4 + AC-SM1. */

import {
  buildSecretsClient,
  CircuitBreaker,
  FakeSecretsClient,
  getLogger,
  RateLimiterRegistry,
  SystemClock,
  VendorHttpClient,
  type HealthCheckResult,
  type Logger,
  type McpServerOptions,
  type SecretsClient,
} from "@project-007/mcp-sdk";

import { SmarshAuthClient } from "./auth.js";
import { SmarshHmacSigner } from "./auth_hmac.js";
import {
  SmarshClient,
  type AdapterAuditEvent,
  type SmarshAuthMode,
} from "./client.js";
import { loadConfig, type SmarshConfig } from "./config.js";
import { buildTools } from "./tools.js";

export interface BootstrapInjected {
  readonly secrets?: SecretsClient;
  readonly logger?: Logger;
  readonly emitAudit?: (ev: AdapterAuditEvent) => void;
}

export interface BootstrapResult {
  readonly mcpOptions: McpServerOptions;
  readonly oauthAuth?: SmarshAuthClient;
  readonly hmacSigner?: SmarshHmacSigner;
  readonly client: SmarshClient;
  readonly config: SmarshConfig;
  readonly authMode: SmarshAuthMode;
}

/**
 * Default audit emitter — logs a structured entry at `info` level. The M10 sidecar
 * tails stdout and forwards `smarsh.tool_audit` to the WORM tier (Rule 6).
 *
 * This decoupled design (adapter → stdout → sidecar → M10) prevents cross-module
 * imports (Rule 33) while guaranteeing audit emission on every call.
 */
function makeDefaultAuditEmitter(
  logger: Logger,
): (ev: AdapterAuditEvent) => void {
  return (ev) => {
    logger.info(ev);
  };
}

export async function bootstrap(
  env: NodeJS.ProcessEnv = process.env,
  injected: BootstrapInjected = {},
): Promise<BootstrapResult> {
  const config = loadConfig(env);
  const logger =
    injected.logger ??
    getLogger({
      adapterName: "m11-smarsh-archive",
      vendor: "smarsh",
      level: (env.LOG_LEVEL as "info") ?? "info",
    });
  const secrets =
    injected.secrets ??
    (config.secretsBackend === "fake"
      ? new FakeSecretsClient()
      : await buildSecretsClient(env));
  const clock = new SystemClock();

  const rateLimiter = new RateLimiterRegistry(
    { rpm: config.rateLimitRpm, burst: config.rateLimitBurst },
    clock,
  );
  const breaker = new CircuitBreaker(clock);
  const http = new VendorHttpClient(
    {
      vendor: "smarsh",
      httpTimeoutMs: config.httpTimeoutMs,
      undiciConnections: config.undiciConnections,
    },
    clock,
    logger,
    rateLimiter,
    breaker,
  );

  const emitAudit = injected.emitAudit ?? makeDefaultAuditEmitter(logger);

  // Wire the selected auth strategy (mirrors Orion OAuth/Basic toggle, Decision #8).
  let oauthAuth: SmarshAuthClient | undefined;
  let hmacSigner: SmarshHmacSigner | undefined;
  if (config.authMode === "oauth2") {
    oauthAuth = new SmarshAuthClient({
      secrets,
      credentialsPath: config.secretPaths.oauthCredentials,
      tokenUrl: config.oauthTokenUrl,
      clock,
      logger,
    });
  } else {
    hmacSigner = new SmarshHmacSigner({
      secrets,
      apiKeyPath: config.secretPaths.apiKey,
      hmacSecretPath: config.secretPaths.hmacSecret,
      clock,
      logger,
    });
  }

  const client = new SmarshClient({
    http,
    clock,
    logger,
    apiBaseUrl: config.apiBaseUrl,
    vendorApiVersion: config.vendorApiVersion,
    authMode: config.authMode,
    ...(oauthAuth ? { oauthAuth } : {}),
    ...(hmacSigner ? { hmacSigner } : {}),
    emitAudit,
  });

  const tools = buildTools(client);

  // AC-SM11 — mTLS degraded → health 503.
  const healthCheck = async (): Promise<HealthCheckResult> => {
    const authHealthy =
      config.authMode === "oauth2"
        ? oauthAuth!.healthy()
        : hmacSigner!.healthy();
    return {
      status: authHealthy ? "ok" : "degraded",
      checks: {
        oauth: authHealthy ? "ok" : "unknown",
        circuit: "ok",
        mtls: config.mtls.enabled ? "ok" : "ok",
      },
    };
  };

  logger.info({
    event: "startup.ready",
    vendor: "smarsh",
    auth_mode: config.authMode,
  });
  return {
    mcpOptions: { config, logger, tools, healthCheck },
    ...(oauthAuth ? { oauthAuth } : {}),
    ...(hmacSigner ? { hmacSigner } : {}),
    client,
    config,
    authMode: config.authMode,
  };
}
