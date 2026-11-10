/**
 * 后端时间字段的解析与展示。
 *
 * 后端存的是 **naive UTC**：``DateTime`` 列不带时区，SQLite 也不保存偏移量，
 * ``isoformat()`` 出来的就是 ``2026-10-12T07:07:05.382492`` 这种没有时区标记的串。
 * JS 的 ``new Date()`` 会把它当**本地时间**解析 —— 在东八区直接差 8 小时，
 * 「3 天前」可能显示成「昨天」，跨天的时间还会显示错日期。
 *
 * 所以要显式补上 ``Z`` 再解析。带时区标记的串（以 Z 或 ±HH:MM 结尾）原样交给 Date。
 */
export function parseUtc(iso?: string | null): number | null {
  if (!iso) return null
  const hasTimezone = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso)
  const ms = new Date(hasTimezone ? iso : `${iso}Z`).getTime()
  return Number.isNaN(ms) ? null : ms
}

/** 本地时区的日期，如 2026/11/11。 */
export function formatDate(iso?: string | null, fallback = '—'): string {
  const ms = parseUtc(iso)
  if (ms === null) return fallback
  return new Date(ms).toLocaleDateString('zh-CN')
}

/** 本地时区的日期时间，如 2026/11/11 15:07。 */
export function formatDateTime(iso?: string | null, fallback = '—'): string {
  const ms = parseUtc(iso)
  if (ms === null) return fallback
  return new Date(ms).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 相对时间，如「3 天前」。 */
export function formatRelative(
  iso?: string | null,
  fallback = '从未'
): string {
  const ms = parseUtc(iso)
  if (ms === null) return fallback

  const diff = Date.now() - ms
  // 客户端时钟比服务端慢时会算出未来时间，归到「刚刚」而不是负数
  if (diff < 60_000) return '刚刚'

  const minutes = Math.floor(diff / 60_000)
  if (minutes < 60) return `${minutes} 分钟前`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`

  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`

  return formatDate(iso)
}
