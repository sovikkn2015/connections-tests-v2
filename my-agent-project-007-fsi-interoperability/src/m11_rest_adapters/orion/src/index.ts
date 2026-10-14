/** Orion adapter entry. */

import { startServer, type ToolDefinition } from "@project-007/mcp-sdk";

import { bootstrap } from "./startup.js";

export { VENDOR_API_VERSION } from "./config.js";
export { bootstrap } from "./startup.js";

let TOOLS_CACHE: Readonly<Record<string, ToolDefinition>> | null = null;

export function TOOLS(): Readonly<Record<string, ToolDefinition>> {
  if (!TOOLS_CACHE) throw new Error("TOOLS() called before bootstrap");
  return TOOLS_CACHE;
}

export async function main(): Promise<void> {
  const b = await bootstrap();
  TOOLS_CACHE = b.mcpOptions.tools;
  await startServer(b.mcpOptions);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    process.stderr.write(
      JSON.stringify({
        event: "fatal_error",
        err: err instanceof Error ? err.message : String(err),
      }) + "\n",
    );
    process.exit(1);
  });
}
