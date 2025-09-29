import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: './dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://127.0.0.1:6080/api',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_WEBSOCKET_URL || 'ws://127.0.0.1:6080/ws/lottery',
        ws: true,
      },
    },
  },
})