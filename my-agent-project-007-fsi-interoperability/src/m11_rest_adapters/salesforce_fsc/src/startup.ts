/**
 * SFDC startup sequence per R17 AC17.1 (v0.2.0).
 */

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

import { SfdcAuthClient } from "./auth.js";
import { SfdcClient } from "./client.js";
import { loadConfig, SFDC_SECRET_PATHS, type SfdcConfig } from "./config.js";
import { buildTools } from "./tools.js";

export interface BootstrapInjected {
  readonly secrets?: SecretsClient;
  readonly logger?: Logger;
  readonly skipVersionCheck?: boolean;
}

export interface BootstrapResult {
  readonly mcpOptions: McpServerOptions;
  readonly auth: SfdcAuthClient;
  readonly client: SfdcClient;
  readonly breaker: CircuitBreaker;
  readonly rateLimiter: RateLimiterRegistry;
  readonly config: SfdcConfig;
}

export async function bootstrap(
  env: NodeJS.ProcessEnv = process.env,
  injected: BootstrapInjected = {},
): Promise<BootstrapResult> {
  const config = loadConfig(env);
  const logger =
    injected.logger ??
    getLogger({
      adapterName: "m11-salesforce-fsc",
      vendor: "salesforce_fsc",
      level: (env.LOG_LEVEL as "info") ?? "info",
    });

  const secrets =
    injected.secrets ??
    (config.secretsBackend === "fake"
      ? new FakeSecretsClient()
      : await buildSecretsClient(env));

  const clock = new SystemClock();

  const auth = new SfdcAuthClient({
    secrets,
    secretPath: SFDC_SECRET_PATHS.oauthCredentials,
    clock,
    logger,
    egressAllowlist: config.egressAllowlist,
  });

  const rateLimiter = new RateLimiterRegistry(
    { rpm: config.rateLimitRpm, burst: config.rateLimitBurst },
    clock,
    config.dailyLimit,
  );
  const breaker = new CircuitBreaker(clock);

  const http = new VendorHttpClient(
    {
      vendor: "salesforce_fsc",
      httpTimeoutMs: config.httpTimeoutMs,
      undiciConnections: config.undiciConnections,
    },
    clock,
    logger,
    rateLimiter,
    breaker,
  );

  const client = new SfdcClient({
    auth,
    http,
    logger,
    vendorApiVersion: config.vendorApiVersion,
  });

  const tools = buildTools(client);

  const healthCheck = async (): Promise<HealthCheckResult> => {
    const oauthOk = auth.healthy();
    return {
      status: oauthOk ? "ok" : "degraded",
      checks: {
        oauth: oauthOk ? "ok" : "unknown",
        circuit: "ok",
        mtls: config.mtls.enabled ? "ok" : "ok",
      },
    };
  };

  const mcpOptions: McpServerOptions = {
    config,
    logger,
    tools,
    healthCheck,
  };

  logger.info({ event: "startup.ready", vendor: "salesforce_fsc" });
  return { mcpOptions, auth, client, breaker, rateLimiter, config };
}
