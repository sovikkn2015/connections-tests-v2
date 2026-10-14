/**
 * Labeled pulsing skeleton for an in-flight tool call.
 * Juniors ship generic spinners; V3 ships per-tool labels (narrative §6).
 */

import type { ToolCall } from '../types/api';

export function SkeletonTool({ tool }: { tool: ToolCall }) {
  return (
    <span
      className="v3-skeleton"
      role="status"
      aria-live="polite"
      aria-label={`Loading ${tool.tool_name}`}
      data-testid={`skeleton-${tool.tool_name}`}
    >
      <span aria-hidden="true">●</span>
      {tool.tool_name}…
    </span>
  );
}
