import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 后端地址可用 VITE_API_TARGET 覆盖，默认本机 8001。
// 用 127.0.0.1 而不是 localhost：Windows 上 localhost 会先解析到 IPv6 的 ::1，
// 而后端默认只监听 IPv4，代理就会连不通（表现为接口 500）
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8001'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/static': {
        target: API_TARGET,
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
          // Markdown 渲染链较大（约 330KB），单独分包：
          // 既避免撑大入口 chunk，也让它能被长期缓存，改动业务代码时不必重下
          'markdown-vendor': [
            'react-markdown',
            'remark-gfm',
            'remark-breaks',
            'rehype-raw',
            'rehype-sanitize',
          ],
        },
      },
    },
  },
})