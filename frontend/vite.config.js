import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to FastAPI so the browser never deals with CORS
// during development. In production the frontend is served statically and
// VITE_API_URL points at the deployed API.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
