import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    open: true,
    headers: {
      'Content-Security-Policy': [
        "default-src 'self'",
        "connect-src 'self' ws://localhost:18789 wss://localhost:18789 wss://*.amazonaws.com https://*.execute-api.*.amazonaws.com https://login.salesforce.com https://*.salesforce.com https://us.cloud.langfuse.com",
        "style-src 'self' 'unsafe-inline'",  // SLDS requires inline styles
        "script-src 'self'",
        "frame-ancestors 'none'",
        "img-src 'self' data:",
        "base-uri 'self'",
        "form-action 'self'",
      ].join('; '),
    },
  },
  publicDir: 'public',
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
