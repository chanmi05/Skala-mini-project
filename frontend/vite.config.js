import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: process.env.AUTH_PROXY_TARGET || 'http://localhost:8080', changeOrigin: true },
      '/voice-api': {
        target: process.env.VOICE_PROXY_TARGET || 'http://localhost:8008',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/voice-api/, ''),
      },
    },
  },
})
