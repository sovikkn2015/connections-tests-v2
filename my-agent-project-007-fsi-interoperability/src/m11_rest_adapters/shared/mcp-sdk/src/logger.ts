/**
 * Structured JSON logger via pino.
 * Spec AC7.1-7.9. Redact PII + tokens. No console.*. No vendor payloads.
 */

import { pino, type Logger as PinoLogger, type LoggerOptions } from "pino";

/** Redact paths — AC7.2. Wildcards for secret-shaped keys. */
export const DEFAULT_REDACT_PATHS: readonly string[] = Object.freeze([
  "password",
  "secret",
  "token",
  "access_token",
  "refresh_token",
  "private_key",
  "privateKey",
  "privateKeyPEM",
  "client_secret",
  "clientSecret",
  "api_key",
  "apiKey",
  "assertion",
  "ssn",
  "taxId",
  "dateOfBirth",
  "dob",
  "req.body.arguments.ssn",
  "req.body.arguments.taxId",
  "req.body.arguments.email",
  "req.body.arguments.dateOfBirth",
  "req.body.arguments.dob",
  "req.headers.authorization",
  "req.headers['x-vendor-token']",
  "err.response.data",
  "*.password",
  "*.secret",
  "*.token",
  "*.access_token",
  "*.refresh_token",
  "*.private_key",
  "*.privateKey",
  "*.privateKeyPEM",
  "*.client_secret",
  "*.clientSecret",
  "*.api_key",
  "*.apiKey",
  "*.assertion",
]);

export interface LoggerOptionsInput {
  readonly adapterName: string;
  readonly vendor: string;
  readonly level?: "trace" | "debug" | "info" | "warn" | "error" | "fatal";
  readonly destination?: NodeJS.WritableStream;
}

/**
 * Build a pino logger with project-wide redact rules.
 * Emits JSON to stdout (default) — sidecar ships to Langfuse + Datadog + M10.
 */
export function getLogger(opts: LoggerOptionsInput): PinoLogger {
  const pinoOpts: LoggerOptions = {
    level: opts.level ?? process.env.LOG_LEVEL ?? "info",
    base: {
      adapter_name: opts.adapterName,
      vendor: opts.vendor,
      pid: process.pid,
    },
    redact: {
      paths: [...DEFAULT_REDACT_PATHS],
      censor: "[REDACTED]",
    },
    timestamp: pino.stdTimeFunctions.isoTime,
    formatters: {
      level: (label) => ({ level: label }),
    },
  };
  return opts.destination ? pino(pinoOpts, opts.destination) : pino(pinoOpts);
}

export type Logger = PinoLogger;
