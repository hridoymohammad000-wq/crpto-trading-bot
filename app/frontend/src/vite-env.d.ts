/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_WS_BASE_URL?: string;
  readonly VITE_BOT_CONTROL_TOKEN?: string;
  readonly VITE_WS_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
