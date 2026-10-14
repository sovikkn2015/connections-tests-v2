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

import { SchwabAuthClient } from "./auth.js";
import { SchwabClient } from "./client.js";
import {
  loadConfig,
  SCHWAB_SECRET_PATHS,
  type SchwabConfig,
} from "./config.js";
import { buildTools } from "./tools.js";

export interface BootstrapInjected {
  readonly secrets?: SecretsClient;
  readonly logger?: Logger;
}

export interface BootstrapResult {
  readonly mcpOptions: McpServerOptions;
  readonly auth: SchwabAuthClient;
  readonly client: SchwabClient;
  readonly config: SchwabConfig;
}

export async function bootstrap(
  env: NodeJS.ProcessEnv = process.env,
  injected: BootstrapInjected = {},
): Promise<BootstrapResult> {
  const config = loadConfig(env);
  const logger =
    injected.logger ?? getLogger({ adapterName: "m11-schwab", vendor: "schwab" });
  const secrets =
    injected.secrets ??
    (config.secretsBackend === "fake"
      ? new FakeSecretsClient()
      : await buildSecretsClient(env));
  const clock = new SystemClock();

  const auth = new SchwabAuthClient({
    secrets,
    credentialsPath: SCHWAB_SECRET_PATHS.oauthCredentials,
    refreshTokenPath: SCHWAB_SECRET_PATHS.refreshToken,
    tokenUrl: config.oauthTokenUrl,
    clock,
    logger,
  });

  const rateLimiter = new RateLimiterRegistry(
    { rpm: config.rateLimitRpm, burst: config.rateLimitBurst },
    clock,
  );
  const breaker = new CircuitBreaker(clock);
  const http = new VendorHttpClient(
    {
      vendor: "schwab",
      httpTimeoutMs: config.httpTimeoutMs,
      undiciConnections: config.undiciConnections,
    },
    clock,
    logger,
    rateLimiter,
    breaker,
  );
  const client = new SchwabClient({
    auth,
    http,
    logger,
    apiBaseUrl: config.apiBaseUrl,
    vendorApiVersion: config.vendorApiVersion,
  });

  const tools = buildTools(client);
  const healthCheck = async (): Promise<HealthCheckResult> => ({
    status: auth.healthy() ? "ok" : "degraded",
    checks: {
      oauth: auth.healthy() ? "ok" : "degraded",
      circuit: "ok",
      mtls: "ok",
    },
  });

  logger.info({ event: "startup.ready", vendor: "schwab" });

  // AC17.3 v0.2.0 — wait for in-flight RT rotation on SIGTERM.
  process.once("SIGTERM", () => {
    logger.info({ event: "sigterm_received", vendor: "schwab" });
    void auth.waitForRotation(10_000);
  });

  return {
    mcpOptions: { config, logger, tools, healthCheck },
    auth,
    client,
    config,
  };
}
