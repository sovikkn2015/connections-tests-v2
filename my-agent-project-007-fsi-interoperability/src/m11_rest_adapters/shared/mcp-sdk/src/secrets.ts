/**
 * SecretsClient interface + Vault + AWS Secrets Manager implementations.
 * Spec R4 — AC4.1-AC4.14. Zero credentials on disk. In-memory only.
 */

export interface CachedSecretMeta {
  readonly expiresAt: number | null;
  readonly rotatedAt: number;
}

export interface SecretsClient {
  /** Fetch an opaque-string secret at `path`. */
  getSecret(path: string): Promise<string>;
  /** Fetch a JSON-structured secret at `path`. */
  getJSONSecret<T = Record<string, unknown>>(path: string): Promise<T>;
  /** Write-back an opaque-string secret (e.g. Schwab rotated RT). */
  setSecret(path: string, value: string): Promise<void>;
  /** True if the secret at `path` should be re-read. */
  refreshRequired(path: string): boolean;
}

/** Pluggable backend selector. */
export type SecretsBackend = "vault" | "aws" | "fake";

/** In-memory fake for unit tests (spec AC4.5, AC16.4). */
export class FakeSecretsClient implements SecretsClient {
  private readonly store: Map<string, string>;
  private readonly refreshPaths: Set<string> = new Set();
  public setSecretCalls: Array<{ path: string; value: string }> = [];
  /** Inject transient setSecret failures for CRITICAL-alert tests (AC4.13). */
  public setSecretFailureCount: number = 0;
  /** Inject getSecret failures for chaos (Task 23). */
  public getSecretFailureCount: number = 0;

  constructor(initial: Record<string, string | object> = {}) {
    this.store = new Map();
    for (const [k, v] of Object.entries(initial)) {
      this.store.set(k, typeof v === "string" ? v : JSON.stringify(v));
    }
  }

  async getSecret(path: string): Promise<string> {
    if (this.getSecretFailureCount > 0) {
      this.getSecretFailureCount--;
      throw new Error("simulated secrets backend 500");
    }
    const v = this.store.get(path);
    if (v === undefined) throw new Error(`secret not found: ${path}`);
    return v;
  }

  async getJSONSecret<T = Record<string, unknown>>(path: string): Promise<T> {
    const raw = await this.getSecret(path);
    try {
      return JSON.parse(raw) as T;
    } catch {
      throw new Error(`secret at ${path} is not JSON`);
    }
  }

  async setSecret(path: string, value: string): Promise<void> {
    if (this.setSecretFailureCount > 0) {
      this.setSecretFailureCount--;
      throw new Error("simulated setSecret failure");
    }
    this.store.set(path, value);
    this.setSecretCalls.push({ path, value });
  }

  refreshRequired(path: string): boolean {
    return this.refreshPaths.has(path);
  }

  // Test helpers (not part of SecretsClient interface).
  markRefreshRequired(path: string): void {
    this.refreshPaths.add(path);
  }
  clearRefresh(path: string): void {
    this.refreshPaths.delete(path);
  }
  rawStore(): ReadonlyMap<string, string> {
    return this.store;
  }
}

/**
 * Select the configured SecretsClient backend at startup.
 * SECRETS_BACKEND must be set (spec AC4.2 — unset → fail).
 */
export async function buildSecretsClient(
  env: NodeJS.ProcessEnv = process.env,
): Promise<SecretsClient> {
  const backend = env.SECRETS_BACKEND as SecretsBackend | undefined;
  if (!backend) {
    throw new Error(
      "SECRETS_BACKEND must be set to 'vault' or 'aws' (spec AC4.2)",
    );
  }
  switch (backend) {
    case "vault": {
      const { VaultSecretsClient } = await import("./secrets_vault.js");
      return new VaultSecretsClient(env);
    }
    case "aws": {
      const { AWSSecretsClient } = await import("./secrets_aws.js");
      return new AWSSecretsClient(env);
    }
    case "fake":
      throw new Error(
        "SECRETS_BACKEND=fake is not allowed at runtime; use FakeSecretsClient directly in tests",
      );
    default:
      throw new Error(`unknown SECRETS_BACKEND: ${String(backend)}`);
  }
}
