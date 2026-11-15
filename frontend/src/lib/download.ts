import { Capacitor } from '@capacitor/core'

/**
 * 保存一个 Blob 为文件，网页端与 App 端统一入口。
 *
 * 为什么需要这个封装
 * ------------------
 * 网页端一直是 `URL.createObjectURL(blob)` + `<a download>` 点击，浏览器
 * 会弹保存框。但在 Android WebView（Capacitor）里，`a[download]` 对
 * blob: 地址**不会触发任何下载**：用户点了没反应，控制台也没有报错。
 *
 * 所以原生环境下改走 `@capacitor/filesystem`：先写到 App 缓存目录，再调
 * 系统分享面板，由用户自行保存到「下载」或发给其它 App。选缓存目录而不是
 * 公共 Documents，是因为 Android 11+ 公共目录已不对普通 App 开放。
 */
export async function downloadBlob(blob: Blob, filename: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    return
  }

  // 延迟引入：网页端不需要这两个插件，避免把它们的代码打进首屏 chunk
  const [{ Filesystem, Directory }, { Share }] = await Promise.all([
    import('@capacitor/filesystem'),
    import('@capacitor/share'),
  ])

  const { uri } = await Filesystem.writeFile({
    path: sanitizeName(filename),
    data: await blobToBase64(blob),
    directory: Directory.Cache,
    recursive: true,
  })

  await Share.share({
    title: filename,
    url: uri,
    dialogTitle: '保存或分享文件',
  })
}

/** 去掉文件名里的路径分隔符与非法字符，避免写文件时抛错 */
function sanitizeName(name: string): string {
  const cleaned = name.replace(/[\\/:*?"<>|]/g, '_').trim()
  return cleaned || `file-${Date.now()}`
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result ?? '')
      // dataURL 形如 data:application/pdf;base64,JVBERi0...，插件只要后半段
      const comma = result.indexOf(',')
      resolve(comma >= 0 ? result.slice(comma + 1) : result)
    }
    reader.onerror = () => reject(reader.error ?? new Error('读取文件失败'))
    reader.readAsDataURL(blob)
  })
}
