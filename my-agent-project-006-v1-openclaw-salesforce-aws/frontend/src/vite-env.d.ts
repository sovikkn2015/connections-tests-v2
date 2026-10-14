/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OPENCLAW_GATEWAY_URL: string;
  readonly VITE_OPENCLAW_GATEWAY_TOKEN: string;
  readonly VITE_AGENTCORE_AUTH_MODE: string;
  readonly VITE_SF_LOGIN_URL: string;
  readonly VITE_SF_CLIENT_ID: string;
  readonly VITE_SF_REDIRECT_URI: string;
  readonly VITE_LANGFUSE_HOST: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
