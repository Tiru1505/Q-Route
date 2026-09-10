import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },

  server: {
    port: 5173,

    // The FastAPI backend will live here later. Until it exists, src/services/api.js
    // serves mock data and never actually hits this proxy.

    proxy: {
      // NOTE: no rewrite. The backend's own routes are already mounted under
      // /api (see app/main.py), so stripping the prefix here produced 404s.

      '/api': {
        // 8010, not 8000: another project on this machine already binds 8000.
        target:
          process.env.VITE_API_TARGET ||
          'http://127.0.0.1:8010',

        changeOrigin: true,
      },
    },
  },
})