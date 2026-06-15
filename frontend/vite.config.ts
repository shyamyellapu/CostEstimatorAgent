import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'https://costestimatorbackend-cdckbnh5gkdsfmgr.centralindia-01.azurewebsites.net',
        changeOrigin: true,
        secure: true,
      },
      '/storage': {
        target: 'https://costestimatorbackend-cdckbnh5gkdsfmgr.centralindia-01.azurewebsites.net',
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
