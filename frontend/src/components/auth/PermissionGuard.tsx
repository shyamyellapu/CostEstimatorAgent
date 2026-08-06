import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { usePermissions } from '../../hooks/usePermissions'

interface PermissionGuardProps {
  permissions: string[]
  /** 'any' (default) requires at least one; 'all' requires every listed permission. */
  mode?: 'any' | 'all'
  children: ReactNode
}

/**
 * Route-level permission guard. This is a UX convenience only — every protected FastAPI endpoint
 * independently re-checks permissions, so hiding a route here does not itself grant or deny
 * backend access.
 */
export default function PermissionGuard({ permissions, mode = 'any', children }: PermissionGuardProps) {
  const { hasAnyPermission, hasAllPermissions } = usePermissions()
  const allowed = mode === 'all' ? hasAllPermissions(permissions) : hasAnyPermission(permissions)
  if (!allowed) {
    return <Navigate to="/unauthorized" replace />
  }
  return <>{children}</>
}
