import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/__tests__/**/*.{test,spec}.{ts,tsx}'],
    env: {
      // Force REST mode in all tests so sendHitlDecision takes the fetch path.
      VITE_AGENT_PROXY_URL: 'https://caodv9yori.execute-api.us-east-1.amazonaws.com/prod/agent/query',
    },
  },
});
