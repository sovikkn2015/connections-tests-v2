/**
 * Compact SLDS-styled table for the expanded end-to-end trace row.
 *
 * Columns: Tool · MCP Server · Data Source · Status · Duration · span id.
 * Column widths are fixed in CSS so the table does not jump when different
 * rows are expanded (demo nit — matches 006 v1 pattern).
 *
 * The tool → MCP / data-source mapping is intentionally tiny and inlined.
 * If `frontend/src/data/toolToNode.ts` ships later (builder 1's scope) we can
 * swap this for that canonical map without changing callers.
 */

import type { ToolCall } from '../types/api';

interface ToolTableProps {
  toolCalls: ToolCall[];
}

/**
 * Best-effort mapping of a tool_name / agent_id pair to an MCP server + data
 * source label. Derived from the 006 topology conventions: skills that end in
 * `_mcp` name their MCP explicitly; specialists carry their data-source in the
 * agent_id prefix. Fallback is "—".
 */
function mcpOf(tool: ToolCall): { mcp: string; source: string } {
  const name = tool.tool_name.toLowerCase();
  const agent = tool.agent_id.toLowerCase();

  if (name.includes('finnhub') || agent.includes('market')) {
    return { mcp: 'finnhub-mcp', source: 'Finnhub' };
  }
  if (name.includes('edgar') || name.includes('sec') || agent.includes('filings')) {
    return { mcp: 'sec-edgar-mcp', source: 'SEC EDGAR' };
  }
  if (name.includes('tavily') || name.includes('news') || agent.includes('sentiment')) {
    return { mcp: 'tavily-mcp', source: 'Tavily News' };
  }
  if (name.includes('crm') || name.includes('salesforce') || agent.includes('advisor')) {
    return { mcp: 'salesforce-mcp', source: 'Salesforce CRM' };
  }
  if (name.includes('compliance') || name.includes('screen')) {
    return { mcp: 'compliance-screen', source: 'Compliance Rules' };
  }
  if (name.includes('mulesoft') || name.includes('ops')) {
    return { mcp: 'mulesoft-mcp', source: 'MuleSoft Ops' };
  }
  return { mcp: '—', source: '—' };
}

function statusGlyph(status: ToolCall['status']): { glyph: string; label: string } {
  switch (status) {
    case 'ok':
      return { glyph: '✓', label: 'OK' };
    case 'error':
      return { glyph: '⨯', label: 'Error' };
    case 'running':
    default:
      return { glyph: '…', label: 'Running' };
  }
}

function formatDuration(ms: number | undefined): string {
  if (ms === undefined || ms === null || Number.isNaN(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function ToolTable({ toolCalls }: ToolTableProps) {
  if (toolCalls.length === 0) {
    return (
      <div className="v3-tool-table__empty" role="note">
        No tool calls recorded for this turn.
      </div>
    );
  }
  return (
    <table
      className="v3-tool-table"
      role="table"
      aria-label="Tool calls for this turn"
    >
      <thead>
        <tr>
          <th scope="col">Tool</th>
          <th scope="col">MCP Server</th>
          <th scope="col">Data Source</th>
          <th scope="col">Status</th>
          <th scope="col">Duration</th>
          <th scope="col">Span</th>
        </tr>
      </thead>
      <tbody>
        {toolCalls.map((tc) => {
          const { mcp, source } = mcpOf(tc);
          const { glyph, label } = statusGlyph(tc.status);
          return (
            <tr key={tc.span_id} data-status={tc.status} data-testid={`tool-row-${tc.span_id}`}>
              <td>{tc.tool_name}</td>
              <td>{mcp}</td>
              <td>{source}</td>
              <td>
                <span
                  className="v3-tool-table__status"
                  data-status={tc.status}
                  aria-label={label}
                  title={label}
                >
                  {glyph} {label}
                </span>
              </td>
              <td>{formatDuration(tc.latency_ms)}</td>
              <td title={tc.span_id} className="v3-tool-table__span">
                {tc.span_id.slice(0, 8)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
