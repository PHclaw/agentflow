import type { CapacitorConfig } from '@capacitor/cli'

/**
 * Capacitor 配置：把 `vite build` 产物打成 Android / iOS 安装包。
 *
 * 关键点
 * ------
 * 1. `webDir: 'dist'` —— 前端静态资源全部打进 App，首屏不依赖网络。
 * 2. `server.androidScheme: 'http'` —— WebView 内页面 origin 是 `http://localhost`，
 *    与后端同为 http，避免「安全上下文请求明文接口」被当作混合内容拦截。
 *    后端上了 HTTPS 之后，这里改回 `https` 并把 `allowMixedContent` 关掉。
 * 3. `allowMixedContent: true` —— 兜底：即便某些 WebView 版本仍按混合内容处理，
 *    也放行 `http://159.75.21.251:3000` 的接口请求。
 * 4. 接口地址不写在这里，走构建期环境变量 `VITE_API_BASE`（见 `.env.capacitor`）。
 */
const config: CapacitorConfig = {
  appId: 'com.agentflow.app',
  appName: 'AgentFlow',
  webDir: 'dist',
  // 默认：打包本地资源（首屏快、弱网可用），接口走 VITE_API_BASE 的绝对地址。
  //
  // 可选：设置环境变量 CAP_SERVER_URL 后改为「直接加载线上站点」，页面与接口
  // 同源，因此完全不涉及 CORS。适用于服务端 CORS 白名单暂时改不了、但需要
  // 立刻能用的场景：
  //   CAP_SERVER_URL=http://159.75.21.251:3000 npm run cap:sync
  server: {
    ...(process.env.CAP_SERVER_URL ? { url: process.env.CAP_SERVER_URL } : {}),
    androidScheme: 'http',
    // 允许 http 明文请求（后端当前是 http://159.75.21.251:3000）
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
  ios: {
    contentInset: 'always',
  },
}

export default config
