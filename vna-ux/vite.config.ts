import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 18300,
    proxy: {
      '/api': {
        target: 'http://localhost:18000',
        changeOrigin: true,
      },
      '/dicom-web': {
        target: 'http://localhost:18042',
        changeOrigin: true,
      },
      '/ohif': {
        target: 'http://localhost:18042',
        changeOrigin: true,
      },
      '/bids-api': {
        target: 'http://localhost:18080',
        changeOrigin: true,
      }
    }
  }
})
