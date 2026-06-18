/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OTA_BASE_URL?: string;
  readonly VITE_OTA_API_KEY?: string;
  readonly VITE_BACKEND_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
