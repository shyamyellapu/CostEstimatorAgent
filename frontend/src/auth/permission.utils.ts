// Pure permission/role-check helpers. Used for UI convenience only (route guards, sidebar
// visibility, button enablement) — the backend independently re-checks every authorization
// decision, so a bypassed frontend check can never grant real access.
import type { AuthUser } from './auth.types'

export function hasRole(user: AuthUser | null, role: string): boolean {
  return !!user && user.role === role
}

export function hasAnyRole(user: AuthUser | null, roles: string[]): boolean {
  return !!user && roles.includes(user.role)
}

export function hasPermission(user: AuthUser | null, permission: string): boolean {
  return !!user && user.permissions.includes(permission)
}

export function hasAnyPermission(user: AuthUser | null, permissions: string[]): boolean {
  return !!user && permissions.some((p) => user.permissions.includes(p))
}

export function hasAllPermissions(user: AuthUser | null, permissions: string[]): boolean {
  return !!user && permissions.every((p) => user.permissions.includes(p))
}
