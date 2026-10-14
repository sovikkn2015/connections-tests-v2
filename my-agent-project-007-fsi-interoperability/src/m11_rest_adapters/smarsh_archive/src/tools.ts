/** Smarsh frozen MCP tool registry — 5 tools. Spec §5 + AC-SM1. */

import type { ToolDefinition } from "@project-007/mcp-sdk";

import type { SmarshClient } from "./client.js";
import {
  ArchiveCaptureInput,
  ArchiveMessageInput,
  GetCaptureStatusInput,
  RetrieveMessageInput,
  SearchMessagesInput,
} from "./schemas.js";

export function buildTools(
  client: SmarshClient,
): Readonly<Record<string, ToolDefinition>> {
  return Object.freeze({
    "smarsh.archive_message": {
      name: "smarsh.archive_message",
      description:
        "Persist a single agent or human communication to Smarsh Professional Archive with SEC 17a-4 retention. Adapter verifies the returned sealed receipt (SHA-256 + sealed_at ±5min) before returning. Returns raw vendor JSON — M7 translator canonicalizes.",
      input: ArchiveMessageInput,
      handler: (args, ctx) =>
        client.archiveMessage(args as never, ctx.firmId),
    },
    "smarsh.retrieve_message": {
      name: "smarsh.retrieve_message",
      description:
        "Retrieve a previously archived message by vendor archive_id. Adapter verifies SHA-256 integrity of retrieved content against the vendor content_hash before returning.",
      input: RetrieveMessageInput,
      handler: (args, ctx) =>
        client.retrieveMessage(args as never, ctx.firmId),
    },
    "smarsh.search_messages": {
      name: "smarsh.search_messages",
      description:
        "Search Smarsh archive within a bounded ≤90-day window. Pagination pass-through — caller re-invokes with the returned next_page_token. Returns raw vendor JSON.",
      input: SearchMessagesInput,
      handler: (args, ctx) =>
        client.searchMessages(args as never, ctx.firmId),
    },
    "smarsh.archive_capture": {
      name: "smarsh.archive_capture",
      description:
        "Upload a base64-encoded attachment to Smarsh Connected Archive with SEC 17a-4 retention. HMAC-SHA256 body signing. Adapter verifies the returned capture receipt (SHA-256 over raw bytes + sealed_at ±5min) before returning. Required for BD deployments (Steering Rule 18).",
      input: ArchiveCaptureInput,
      handler: (args, ctx) =>
        client.archiveCapture(args as never, ctx.firmId),
    },
    "smarsh.get_capture_status": {
      name: "smarsh.get_capture_status",
      description:
        "Retrieve processing status of a previously-uploaded Smarsh Connected Archive capture. HMAC-SHA256 signed GET. Returns raw vendor JSON with status / updated_at / retention details.",
      input: GetCaptureStatusInput,
      handler: (args, ctx) =>
        client.getCaptureStatus(args as never, ctx.firmId),
    },
  });
}
