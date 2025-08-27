import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/health': {
        target: process.env.VITE_API_BASE || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});

