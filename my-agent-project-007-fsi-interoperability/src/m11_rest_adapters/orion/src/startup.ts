/** Orion startup — builds auth branch per ORION_AUTH_MODE (AC4.12). */

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

import {
  OrionBasicStrategy,
  OrionOAuthStrategy,
  type BaseAuthStrategy,
} from "./auth.js";
import { OrionClient } from "./client.js";
import { loadConfig, ORION_SECRET_PATHS, type OrionConfig } from "./config.js";
import { buildTools } from "./tools.js";

export interface BootstrapInjected {
  readonly secrets?: SecretsClient;
  readonly logger?: Logger;
}

export interface BootstrapResult {
  readonly mcpOptions: McpServerOptions;
  readonly auth: BaseAuthStrategy;
  readonly client: OrionClient;
  readonly config: OrionConfig;
}

export async function bootstrap(
  env: NodeJS.ProcessEnv = process.env,
  injected: BootstrapInjected = {},
): Promise<BootstrapResult> {
  const config = loadConfig(env);
  const logger =
    injected.logger ??
    getLogger({
      adapterName: "m11-orion",
      vendor: "orion",
      level: (env.LOG_LEVEL as "info") ?? "info",
    });
  const secrets =
    injected.secrets ??
    (config.secretsBackend === "fake"
      ? new FakeSecretsClient()
      : await buildSecretsClient(env));
  const clock = new SystemClock();

  let auth: BaseAuthStrategy;
  if (config.authMode === "basic") {
    const b = new OrionBasicStrategy({
      secrets,
      secretPath: ORION_SECRET_PATHS.basicCredentials,
      logger,
    });
    await b.init();
    auth = b;
  } else {
    auth = new OrionOAuthStrategy({
      secrets,
      secretPath: ORION_SECRET_PATHS.oauthCredentials,
      clock,
      logger,
    });
  }

  const rateLimiter = new RateLimiterRegistry(
    { rpm: config.rateLimitRpm, burst: config.rateLimitBurst },
    clock,
  );
  const breaker = new CircuitBreaker(clock);
  const http = new VendorHttpClient(
    {
      vendor: "orion",
      httpTimeoutMs: config.httpTimeoutMs,
      undiciConnections: config.undiciConnections,
    },
    clock,
    logger,
    rateLimiter,
    breaker,
  );
  const client = new OrionClient({
    auth,
    http,
    logger,
    apiBaseUrl: config.apiBaseUrl,
  });

  const tools = buildTools(client);

  const healthCheck = async (): Promise<HealthCheckResult> => ({
    status: auth.healthy() ? "ok" : "degraded",
    checks: {
      oauth: auth.healthy() ? "ok" : "unknown",
      circuit: "ok",
      mtls: "ok",
    },
  });

  logger.info({
    event: "startup.ready",
    vendor: "orion",
    auth_mode: config.authMode,
  });
  return {
    mcpOptions: { config, logger, tools, healthCheck },
    auth,
    client,
    config,
  };
}
