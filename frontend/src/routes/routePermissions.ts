// Central mapping of application routes to their required permissions/roles. Used both to wrap
// routes with guards in AppRoutes/App.tsx and to filter Sidebar entries — keeping the two in sync
// in one place instead of duplicating the rules.
import { PERMISSIONS, ROLES } from '../auth/auth.constants'

export interface RoutePermissionRule {
  path: string
  permissions?: string[]
  roles?: string[]
}

export const ROUTE_PERMISSIONS: RoutePermissionRule[] = [
  { path: '/dashboard', permissions: [PERMISSIONS.DASHBOARD_READ] },
  { path: '/estimate/new', permissions: [PERMISSIONS.ESTIMATES_CREATE] },
  { path: '/drawing-costing', permissions: [PERMISSIONS.DRAWINGS_PROCESS] },
  { path: '/weight-calculator', roles: [ROLES.ESTIMATOR, ROLES.MANAGER, ROLES.ADMIN] },
  { path: '/boq-parser', permissions: [PERMISSIONS.BOQ_PARSE] },
  { path: '/excel-generator', permissions: [PERMISSIONS.EXCEL_GENERATE] },
  { path: '/quote-summary', permissions: [PERMISSIONS.QUOTATIONS_READ] },
  { path: '/cover-letter', permissions: [PERMISSIONS.COVER_LETTERS_GENERATE] },
  { path: '/rfq', permissions: [PERMISSIONS.RFQ_READ] },
  { path: '/history', permissions: [PERMISSIONS.JOB_HISTORY_READ] },
  { path: '/settings', permissions: [PERMISSIONS.SETTINGS_READ] },
  { path: '/admin/users', permissions: [PERMISSIONS.USERS_READ] },
  { path: '/admin/sessions', permissions: [PERMISSIONS.SESSIONS_READ] },
  { path: '/admin/audit-logs', permissions: [PERMISSIONS.AUDIT_LOGS_READ] },
]

export function getRouteRule(path: string): RoutePermissionRule | undefined {
  return ROUTE_PERMISSIONS.find((r) => r.path === path)
}
