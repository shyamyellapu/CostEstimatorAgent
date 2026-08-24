import { useAuth } from './useAuth'
import { hasAllPermissions, hasAnyPermission, hasAnyRole, hasPermission, hasRole } from '../auth/permission.utils'

/** Convenience hook bundling the current user + permission-check helpers for UI code. */
export function usePermissions() {
  const { user } = useAuth()
  return {
    user,
    hasRole: (role: string) => hasRole(user, role),
    hasAnyRole: (roles: string[]) => hasAnyRole(user, roles),
    hasPermission: (permission: string) => hasPermission(user, permission),
    hasAnyPermission: (permissions: string[]) => hasAnyPermission(user, permissions),
    hasAllPermissions: (permissions: string[]) => hasAllPermissions(user, permissions),
  }
}
