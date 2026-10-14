/**
 * AWS Secrets Manager implementation of SecretsClient. Spec R4 AC4.2.
 */

import type { SecretsClient } from "./secrets.js";

interface AwsLikeClient {
  send<T>(cmd: unknown): Promise<T>;
}

type CmdCtor<P> = new (p: P) => unknown;

export class AWSSecretsClient implements SecretsClient {
  private readonly client: AwsLikeClient;
  private readonly GetCmd: CmdCtor<{ SecretId: string }>;
  private readonly PutCmd: CmdCtor<{ SecretId: string; SecretString: string }>;

  constructor(
    env: NodeJS.ProcessEnv,
    injected?: {
      client: AwsLikeClient;
      GetCmd: CmdCtor<{ SecretId: string }>;
      PutCmd: CmdCtor<{ SecretId: string; SecretString: string }>;
    },
  ) {
    if (injected) {
      this.client = injected.client;
      this.GetCmd = injected.GetCmd;
      this.PutCmd = injected.PutCmd;
      return;
    }
    const region = env.AWS_REGION ?? env.AWS_DEFAULT_REGION;
    if (!region) {
      throw new Error("AWS_REGION must be set for AWS Secrets backend (AC4.2)");
    }
    // Lazy require — only pulled in when backend=aws at runtime.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const sdk = require("@aws-sdk/client-secrets-manager");
    this.client = new sdk.SecretsManagerClient({ region }) as AwsLikeClient;
    this.GetCmd = sdk.GetSecretValueCommand as CmdCtor<{ SecretId: string }>;
    this.PutCmd = sdk.PutSecretValueCommand as CmdCtor<{
      SecretId: string;
      SecretString: string;
    }>;
  }

  async getSecret(path: string): Promise<string> {
    const cmd = new this.GetCmd({ SecretId: path });
    const res = await this.client.send<{ SecretString?: string }>(cmd);
    if (typeof res.SecretString !== "string") {
      throw new Error(`aws secret at ${path} has no SecretString`);
    }
    return res.SecretString;
  }

  async getJSONSecret<T = Record<string, unknown>>(path: string): Promise<T> {
    const raw = await this.getSecret(path);
    try {
      return JSON.parse(raw) as T;
    } catch {
      throw new Error(`aws secret at ${path} is not JSON`);
    }
  }

  async setSecret(path: string, value: string): Promise<void> {
    const cmd = new this.PutCmd({ SecretId: path, SecretString: value });
    await this.client.send(cmd);
  }

  refreshRequired(_path: string): boolean {
    return false;
  }
}
