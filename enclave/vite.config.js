import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [
    react({
      // Fast Refresh configuration
      fastRefresh: true,
      // Skip building React DevTools in production
      exclude: /node_modules/
    })
  ],
  root: path.resolve(__dirname, 'src/frontend'),
  build: {
    outDir: path.resolve(__dirname, 'src/frontend/dist'),
    emptyOutDir: true,
    // Optimize build performance
    target: 'es2015',
    minify: 'esbuild',
    sourcemap: false,
    reportCompressedSize: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          utils: ['lodash', 'axios']
        }
      }
    }
  },
  server: {
    port: 3000,
    host: true,
    hmr: {
      overlay: false
    },
    proxy: {
      '/api': {
        target: 'http://localhost:6080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:6080',
        ws: true,
      },
    },
  },
  // Optimize dependency pre-bundling
  optimizeDeps: {
    include: ['react', 'react-dom'],
    exclude: ['@vite/client', '@vite/env']
  },
  // Faster CSS processing
  css: {
    devSourcemap: false
  },
  // Reduce file system checks
  resolve: {
    symlinks: false
  }
})