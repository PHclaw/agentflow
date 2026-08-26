import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, token } = useAuthStore()
  const location = useLocation()
  const hasToken = isAuthenticated || !!token || !!localStorage.getItem('token')

  if (!hasToken) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
