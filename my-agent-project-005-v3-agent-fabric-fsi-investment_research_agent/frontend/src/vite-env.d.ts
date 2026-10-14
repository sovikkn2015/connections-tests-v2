/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SF_LOGIN_URL: string;
  readonly VITE_SF_CLIENT_ID: string;
  readonly VITE_SF_REDIRECT_URI: string;
  readonly VITE_SF_AGENT_ID: string;
  readonly VITE_API_GATEWAY_URL: string;
  readonly VITE_AWS_API_KEY: string;
  // V3 Agent Fabric
  readonly VITE_FLEX_GATEWAY_URL: string;
  readonly VITE_ANYPOINT_VISUALIZER_URL: string;
  readonly VITE_ANYPOINT_VISUALIZER_API: string;
  readonly VITE_ANYPOINT_ORG_ID: string;
  readonly VITE_AGENT_ID: string;
  // Observability
  readonly VITE_LANGFUSE_PUBLIC_KEY: string;
  readonly VITE_LANGFUSE_HOST: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
