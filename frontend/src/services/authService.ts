// Thin wrapper around the /auth/* and /admin/* HTTP endpoints. Kept separate from AuthProvider so
// the network layer can be unit-tested / mocked independently of React state.
import { api } from '../api/client'
import type { AuthUser, LoginResponse } from '../auth/auth.types'

export interface SessionOut {
  id: string
  device_name: string | null
  browser: string | null
  operating_system: string | null
  ip_address: string | null
  created_at: string
  last_activity_at: string | null
  expires_at: string
  is_current: boolean
}

export const authService = {
  async register(payload: { email: string; username: string; full_name: string; password: string }): Promise<AuthUser> {
    const res = await api.post<AuthUser>('/auth/register', payload)
    return res.data
  },

  async login(payload: { identifier: string; password: string; remember_me?: boolean }): Promise<LoginResponse> {
    const res = await api.post<LoginResponse>('/auth/login', payload)
    return res.data
  },

  async refresh(): Promise<LoginResponse> {
    const res = await api.post<LoginResponse>('/auth/refresh')
    return res.data
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout')
  },

  async logoutAll(): Promise<void> {
    await api.post('/auth/logout-all')
  },

  async me(): Promise<AuthUser> {
    const res = await api.get<AuthUser>('/auth/me')
    return res.data
  },

  async changePassword(payload: { current_password: string; new_password: string }): Promise<void> {
    await api.post('/auth/change-password', payload)
  },

  async forgotPassword(email: string): Promise<{ message: string }> {
    const res = await api.post<{ message: string }>('/auth/forgot-password', { email })
    return res.data
  },

  async resetPassword(payload: { token: string; new_password: string }): Promise<{ message: string }> {
    const res = await api.post<{ message: string }>('/auth/reset-password', payload)
    return res.data
  },

  async listSessions(): Promise<SessionOut[]> {
    const res = await api.get<SessionOut[]>('/auth/sessions')
    return res.data
  },

  async revokeSession(sessionId: string): Promise<void> {
    await api.delete(`/auth/sessions/${sessionId}`)
  },

  async revokeAllOtherSessions(): Promise<void> {
    await api.delete('/auth/sessions')
  },
}
