/// <reference types="vite/client" />

/**
 * 构建期注入的环境变量。
 *
 * 之前缺这个文件，`import.meta.env` 在 `tsc` 下是未声明属性；补上之后
 * 网页端（不设任何变量）与 App 构建（注入绝对地址）共用同一份源码。
 */
interface ImportMetaEnv {
  /**
   * 后端接口基地址。
   *
   * - 留空：走同源相对路径 `/api/v1`，由 Vite dev proxy / nginx 转发（网页端默认）
   * - 绝对地址：如 `http://159.75.21.251:3000/api/v1`，Capacitor 打包 APK 时必填
   */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
