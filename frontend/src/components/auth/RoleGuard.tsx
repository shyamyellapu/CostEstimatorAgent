import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { usePermissions } from '../../hooks/usePermissions'

interface RoleGuardProps {
  roles: string[]
  children: ReactNode
}

/** Authenticated-but-unauthorized users are redirected to /unauthorized — never back to /login. */
export default function RoleGuard({ roles, children }: RoleGuardProps) {
  const { hasAnyRole } = usePermissions()
  if (!hasAnyRole(roles)) {
    return <Navigate to="/unauthorized" replace />
  }
  return <>{children}</>
}
