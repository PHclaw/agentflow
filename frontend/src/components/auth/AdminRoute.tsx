import { Navigate } from 'react-router-dom'
import { useAuthStore, useIsAdmin } from '../../stores'

/**
 * 管理员路由守卫。
 *
 * **这只是体验层**：让非管理员看不到、进不去后台，避免误点后拿到一屏 403。
 * 真正的权限在后端 ``require_admin`` —— 前端守卫改个 localStorage 就能绕过，
 * 所以后端必须独立校验，这里不做任何安全承诺。
 */
export function AdminRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.token) || localStorage.getItem('token')
  const isAdmin = useIsAdmin()

  if (!token) {
    return <Navigate to="/login" replace />
  }

  // 角色还没拿到就先等一下。两种情况会走到这里：
  // 1. 刚刷新页面，fetchMe 还没返回；
  // 2. 本地持久化的 user 是旧版本的（没有 role 字段）。
  // 直接判定为非管理员会把人踢回首页，管理员每次刷新都要手动点回来。
  if (!user || user.role === undefined) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-slate-500 dark:text-slate-400">
        正在校验权限…
      </div>
    )
  }

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}
