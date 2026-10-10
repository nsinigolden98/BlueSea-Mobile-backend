import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Served by the Rust backend under /admin (see src/admin/). `base` keeps
// built asset URLs inside /admin/... In dev, /admin/api/* proxies to Axum.
export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  server: {
    proxy: {
      '/admin/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
