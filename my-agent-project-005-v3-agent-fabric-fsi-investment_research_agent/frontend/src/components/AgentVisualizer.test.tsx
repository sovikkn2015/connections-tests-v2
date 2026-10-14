/**
 * Component test for AgentVisualizer — renders in the empty state with
 * the expected 6-node chain and empty-event message.
 */

import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../test/msw-server';
import AgentVisualizer from './AgentVisualizer';

describe('<AgentVisualizer />', () => {
  it('shows the empty-state event message when no traces are returned', async () => {
    // Both providers 500 → stub source → empty events list.
    server.use(
      http.get('https://anypoint.example/api/traces/:cid', () => new HttpResponse(null, { status: 500 })),
      http.get('https://langfuse.example/api/public/traces', () => new HttpResponse(null, { status: 500 })),
    );

    render(<AgentVisualizer />);

    expect(screen.getByText('Agent Visualizer')).toBeInTheDocument();
    expect(screen.getByText('Analyst')).toBeInTheDocument();
    expect(screen.getByText('Agentforce')).toBeInTheDocument();
    expect(screen.getByText('Flex Gateway')).toBeInTheDocument();
    expect(screen.getByText('MCP Server')).toBeInTheDocument();
    expect(screen.getByText('Data Source')).toBeInTheDocument();
    expect(screen.getByText('Response')).toBeInTheDocument();

    await waitFor(() =>
      expect(
        screen.getByText('No events yet — run a query to populate the trace.'),
      ).toBeInTheDocument(),
    );
  });
});
