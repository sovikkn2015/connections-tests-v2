/**
 * Unit tests for the tool-name → topology-node-id resolver.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { resolveNodeId } from '../../../src/shared/data/toolToNode';

describe('resolveNodeId', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('resolves a known skill tool to its skill: node id', () => {
    expect(resolveNodeId('rag_retrieve')).toBe('skill:rag_retrieve');
    expect(resolveNodeId('compliance_screening')).toBe('skill:compliance_screening');
    expect(resolveNodeId('hitl')).toBe('skill:hitl');
    expect(resolveNodeId('mulesoft_api')).toBe('skill:mulesoft_api');
  });

  it('resolves a known MCP tool to its MCP node id', () => {
    expect(resolveNodeId('run_soql_query')).toBe('salesforce-crm');
    expect(resolveNodeId('get_quote')).toBe('market-data');
    expect(resolveNodeId('get_10k')).toBe('sec-edgar');
    expect(resolveNodeId('search_financial_news')).toBe('news-search');
    expect(resolveNodeId('submit_order')).toBe('mulesoft-actions');
  });

  it('returns null for an unknown tool and emits a dev-mode console.warn', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const result = resolveNodeId('totally_unknown_tool_xyz');
    expect(result).toBeNull();
    expect(warn).toHaveBeenCalled();
  });

  it('uses persona hint as a fallback when the tool is unknown but a persona is supplied', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    // Persona hint should resolve to salesforce-crm for the advisor persona.
    expect(resolveNodeId('some_mystery_read', 'fsi_advisor')).toBe('salesforce-crm');
    // Without a persona hint, same input would warn + return null.
    expect(warn).not.toHaveBeenCalled();
  });

  it('is case-insensitive for exact tool-name matches', () => {
    expect(resolveNodeId('GET_QUOTE')).toBe('market-data');
    expect(resolveNodeId('Rag_Retrieve')).toBe('skill:rag_retrieve');
    expect(resolveNodeId('SUBMIT_ORDER')).toBe('mulesoft-actions');
  });

  it('falls back to substring heuristics for close-but-not-exact tool names', () => {
    expect(resolveNodeId('edgar_deep_fetch')).toBe('sec-edgar');
    expect(resolveNodeId('tavily_top_news')).toBe('news-search');
    expect(resolveNodeId('salesforce_update_contact')).toBe('salesforce-crm');
  });

  it('returns null for an empty string', () => {
    expect(resolveNodeId('')).toBeNull();
  });
});
