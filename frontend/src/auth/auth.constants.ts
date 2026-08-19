// Central place for auth-related constants shared across the frontend.

export const ROLES = {
  ADMIN: 'admin',
  MANAGER: 'manager',
  ESTIMATOR: 'estimator',
  USER: 'user',
} as const

export type Role = (typeof ROLES)[keyof typeof ROLES]

export const PERMISSIONS = {
  DASHBOARD_READ: 'dashboard.read',
  ESTIMATES_CREATE: 'estimates.create',
  ESTIMATES_READ: 'estimates.read',
  ESTIMATES_UPDATE: 'estimates.update',
  ESTIMATES_DELETE: 'estimates.delete',
  DRAWINGS_PROCESS: 'drawings.process',
  BOQ_PARSE: 'boq.parse',
  QUOTATIONS_GENERATE: 'quotations.generate',
  QUOTATIONS_READ: 'quotations.read',
  EXCEL_GENERATE: 'excel.generate',
  COVER_LETTERS_GENERATE: 'cover_letters.generate',
  RFQ_READ: 'rfq.read',
  RFQ_MANAGE: 'rfq.manage',
  JOB_HISTORY_READ: 'job_history.read',
  USERS_READ: 'users.read',
  USERS_CREATE: 'users.create',
  USERS_UPDATE: 'users.update',
  USERS_DISABLE: 'users.disable',
  USERS_ASSIGN_ROLE: 'users.assign_role',
  SESSIONS_READ: 'sessions.read',
  SESSIONS_REVOKE: 'sessions.revoke',
  SETTINGS_READ: 'settings.read',
  SETTINGS_UPDATE: 'settings.update',
  AUDIT_LOGS_READ: 'audit_logs.read',
} as const

// Silent-refresh scheduling: refresh this many seconds before the access token actually expires.
export const REFRESH_BUFFER_SECONDS = 60

export const CSRF_COOKIE_NAME = 'cost_estimator_csrf'
export const CSRF_HEADER_NAME = 'X-CSRF-Token'
