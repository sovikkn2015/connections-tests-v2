/**
 * HashiCorp Vault implementation of SecretsClient. Spec R4 AC4.2.
 * Lazy-imports `node-vault` to avoid pulling it into unit-test bundles.
 */

import type { SecretsClient } from "./secrets.js";

interface VaultLikeClient {
  read(path: string): Promise<{ data?: Record<string, unknown>; [k: string]: unknown }>;
  write(path: string, body: Record<string, unknown>): Promise<unknown>;
}

export class VaultSecretsClient implements SecretsClient {
  private readonly client: VaultLikeClient;

  constructor(env: NodeJS.ProcessEnv, injected?: VaultLikeClient) {
    if (injected) {
      this.client = injected;
      return;
    }
    const endpoint = env.VAULT_ADDR;
    const vaultToken = env.VAULT_TOKEN;
    if (!endpoint || !vaultToken) {
      throw new Error(
        "VAULT_ADDR and VAULT_TOKEN must be set for Vault backend (AC4.2)",
      );
    }
    // Lazy require — only pulled in when backend=vault at runtime.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const vault = require("node-vault");
    this.client = vault({ endpoint, token: vaultToken }) as VaultLikeClient;
  }

  async getSecret(path: string): Promise<string> {
    const res = await this.client.read(path);
    const data = (res.data as Record<string, unknown> | undefined) ?? {};
    const v = (data as { value?: unknown }).value;
    if (typeof v !== "string") {
      throw new Error(`vault secret at ${path} lacks string "value"`);
    }
    return v;
  }

  async getJSONSecret<T = Record<string, unknown>>(path: string): Promise<T> {
    const res = await this.client.read(path);
    const data = res.data as T | undefined;
    if (data === undefined) {
      throw new Error(`vault secret at ${path} has no data`);
    }
    return data;
  }

  async setSecret(path: string, value: string): Promise<void> {
    await this.client.write(path, { value });
  }

  refreshRequired(_path: string): boolean {
    return false;
  }
}
