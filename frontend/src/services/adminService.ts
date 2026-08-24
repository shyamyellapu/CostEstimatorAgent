// Admin-only API calls (user management, session oversight, audit log viewing).
import { api } from '../api/client'

export interface AdminUser {
  id: string
  email: string
  username: string
  full_name: string
  role: string | null
  is_active: boolean
  is_verified: boolean
  last_login: string | null
  created_at: string
  updated_at: string | null
}

export interface AdminUserListResponse {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

export interface AdminSession {
  id: string
  user_id: string
  user_email: string | null
  device_name: string | null
  browser: string | null
  operating_system: string | null
  ip_address: string | null
  created_at: string
  last_activity_at: string | null
  expires_at: string
}

export interface RoleOut {
  id: string
  name: string
  description: string | null
  is_system_role: boolean
}

export interface AuditLogEntry {
  id: string
  user_id: string | null
  action: string
  status: string
  ip_address: string | null
  request_id: string | null
  timestamp: string
  metadata_json: Record<string, unknown> | null
}

export interface AuditLogListResponse {
  items: AuditLogEntry[]
  total: number
  page: number
  page_size: number
}

export const adminService = {
  async listUsers(params: { search?: string; role?: string; is_active?: boolean; page?: number; page_size?: number }): Promise<AdminUserListResponse> {
    const res = await api.get<AdminUserListResponse>('/admin/users', { params })
    return res.data
  },

  async createUser(payload: { email: string; username: string; full_name: string; password: string; role: string }): Promise<AdminUser> {
    const res = await api.post<AdminUser>('/admin/users', payload)
    return res.data
  },

  async assignRole(userId: string, role: string): Promise<AdminUser> {
    const res = await api.patch<AdminUser>(`/admin/users/${userId}/role`, { role })
    return res.data
  },

  async setStatus(userId: string, isActive: boolean): Promise<AdminUser> {
    const res = await api.patch<AdminUser>(`/admin/users/${userId}/status`, { is_active: isActive })
    return res.data
  },

  async listRoles(): Promise<RoleOut[]> {
    const res = await api.get<RoleOut[]>('/admin/roles')
    return res.data
  },

  async listAllSessions(): Promise<AdminSession[]> {
    const res = await api.get<AdminSession[]>('/admin/sessions')
    return res.data
  },

  async revokeSession(sessionId: string): Promise<void> {
    await api.delete(`/admin/sessions/${sessionId}`)
  },

  async listAuditLogs(params: { page?: number; page_size?: number }): Promise<AuditLogListResponse> {
    const res = await api.get<AuditLogListResponse>('/admin/audit-logs', { params })
    return res.data
  },
}
