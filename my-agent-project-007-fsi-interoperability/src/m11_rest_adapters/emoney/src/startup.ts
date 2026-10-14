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

import { EMoneyAuthClient } from "./auth.js";
import { EMoneyClient } from "./client.js";
import { EMONEY_SECRET_PATHS, loadConfig, type EMoneyConfig } from "./config.js";
import { buildTools } from "./tools.js";

export interface BootstrapInjected {
  readonly secrets?: SecretsClient;
  readonly logger?: Logger;
}

export interface BootstrapResult {
  readonly mcpOptions: McpServerOptions;
  readonly auth: EMoneyAuthClient;
  readonly client: EMoneyClient;
  readonly config: EMoneyConfig;
}

export async function bootstrap(
  env: NodeJS.ProcessEnv = process.env,
  injected: BootstrapInjected = {},
): Promise<BootstrapResult> {
  const config = loadConfig(env);
  const logger =
    injected.logger ?? getLogger({ adapterName: "m11-emoney", vendor: "emoney" });
  const secrets =
    injected.secrets ??
    (config.secretsBackend === "fake"
      ? new FakeSecretsClient()
      : await buildSecretsClient(env));
  const clock = new SystemClock();

  const auth = new EMoneyAuthClient({
    secrets,
    secretPath: EMONEY_SECRET_PATHS.oauthCredentials,
    clock,
    logger,
    requiredScope: config.requiredScope,
  });

  const rateLimiter = new RateLimiterRegistry(
    { rpm: config.rateLimitRpm, burst: config.rateLimitBurst },
    clock,
  );
  const breaker = new CircuitBreaker(clock);
  const http = new VendorHttpClient(
    {
      vendor: "emoney",
      httpTimeoutMs: config.httpTimeoutMs,
      undiciConnections: config.undiciConnections,
    },
    clock,
    logger,
    rateLimiter,
    breaker,
  );
  const client = new EMoneyClient({
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
      oauth: auth.healthy() ? "ok" : "unknown",
      circuit: "ok",
      mtls: "ok",
    },
  });

  logger.info({ event: "startup.ready", vendor: "emoney" });
  return { mcpOptions: { config, logger, tools, healthCheck }, auth, client, config };
}
