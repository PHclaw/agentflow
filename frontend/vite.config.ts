import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // 用 127.0.0.1 而不是 localhost：Windows 上 localhost 会先解析到 IPv6 的 ::1，
        // 而后端默认只监听 IPv4，代理就会连不通（表现为接口 500）
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['zustand', 'lucide-react'],
          'flow-vendor': ['reactflow'],
        },
      },
    },
  },
})