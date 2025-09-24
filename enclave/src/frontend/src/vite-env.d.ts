/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LOTTERY_CONTRACT_ADDRESS: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_WEBSOCKET_URL: string
  // Add more env variables as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}