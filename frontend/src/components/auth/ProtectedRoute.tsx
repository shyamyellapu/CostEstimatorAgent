import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

/**
 * Guards a route behind authentication. Renders nothing (a loading state) until session
 * restoration finishes — protected content must never flash before we know whether the user is
 * actually authenticated.
 */
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isInitializing, isAuthenticated } = useAuth()
  const location = useLocation()

  if (isInitializing) {
    console.info('[auth] ProtectedRoute: auth still initializing, holding at', location.pathname)
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="spinner spinner-lg" />
      </div>
    )
  }

  if (!isAuthenticated) {
    console.info('[auth] ProtectedRoute: not authenticated, redirecting to /login from', location.pathname)
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
