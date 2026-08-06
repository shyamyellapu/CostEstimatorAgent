import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, setAccessToken, setOnAuthFailure, setRefreshHandler, triggerRefresh } from '../api/client'
import { authService } from '../services/authService'
import { REFRESH_BUFFER_SECONDS } from './auth.constants'
import type { AuthStatus, AuthUser } from './auth.types'

// Minimum time between visibility-triggered refresh attempts, so rapidly flipping tabs can't
// spam the refresh endpoint (it's also deduped by triggerRefresh's single-flight, but this avoids
// even attempting it).
const MIN_VISIBILITY_REFRESH_INTERVAL_MS = 15_000

export interface AuthContextValue {
  status: AuthStatus
  isInitializing: boolean
  isAuthenticated: boolean
  user: AuthUser | null
  authenticationError: string | null
  sessionExpired: boolean
  login: (identifier: string, password: string, rememberMe?: boolean) => Promise<void>
  register: (payload: { email: string; username: string; full_name: string; password: string }) => Promise<void>
  logout: () => Promise<void>
  logoutAll: () => Promise<void>
  refreshSession: () => Promise<string>
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
  hasRole: (role: string) => boolean
  hasPermission: (permission: string) => boolean
  clearAuthenticationError: () => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null)

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('initializing')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authenticationError, setAuthenticationError] = useState<string | null>(null)
  const [sessionExpired, setSessionExpired] = useState(false)

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Guards the startup-restore effect against React 18 StrictMode's dev-only double-invoke, which
  // would otherwise fire two concurrent /auth/refresh calls on mount.
  const startupRestoreStartedRef = useRef(false)
  const lastVisibilityRefreshAtRef = useRef(0)
  const navigate = useNavigate()

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
      refreshTimerRef.current = null
    }
  }, [])

  const scheduleRefresh = useCallback((expiresInSeconds: number) => {
    clearRefreshTimer()
    const delayMs = Math.max((expiresInSeconds - REFRESH_BUFFER_SECONDS) * 1000, 5_000)
    console.info(`[auth] scheduling proactive refresh in ${Math.round(delayMs / 1000)}s`)
    refreshTimerRef.current = setTimeout(() => {
      // Skip proactive refresh while the tab is hidden; refresh on visibility instead (below).
      if (document.visibilityState === 'hidden') return
      console.info('[auth] proactive refresh timer fired')
      // Routed through triggerRefresh so this never races the interceptor's 401-triggered refresh
      // or the visibility-change refresh — only one network call is ever in flight.
      void triggerRefresh().catch(() => {
        /* handled inside refreshSession */
      })
    }, delayMs)
  }, [clearRefreshTimer])

  const refreshSession = useCallback(async (): Promise<string> => {
    console.info('[auth] refreshSession: calling /auth/refresh')
    try {
      const data = await authService.refresh()
      setAccessToken(data.access_token)
      setUser(data.user)
      setStatus('authenticated')
      setSessionExpired(false)
      scheduleRefresh(data.expires_in)
      console.info('[auth] refreshSession: succeeded, user restored:', data.user?.username)
      return data.access_token
    } catch (err) {
      // A network/timeout/CORS failure means we simply couldn't reach the server — it says
      // nothing about whether the session is still valid, so don't force a logout for it. Only a
      // definitive server response (expired/invalid/reused refresh token, revoked session, etc.)
      // should end the session.
      if (err instanceof ApiError && err.isNetworkError) {
        console.warn('[auth] refreshSession: network error, keeping current auth state:', err.message)
        throw err
      }
      console.warn('[auth] refreshSession: failed, logging out:', err)
      setAccessToken(null)
      setUser(null)
      setStatus('unauthenticated')
      clearRefreshTimer()
      throw err
    }
  }, [clearRefreshTimer, scheduleRefresh])

  // Register the axios refresh handler + auth-failure callback once.
  useEffect(() => {
    setRefreshHandler(refreshSession)
    setOnAuthFailure((error: unknown) => {
      if (error instanceof ApiError && error.isNetworkError) {
        // Never log out for a network hiccup — the interceptor already rejected the original
        // request; the user can simply retry once connectivity returns.
        console.warn('[auth] onAuthFailure: network error, not logging out')
        return
      }
      console.warn('[auth] onAuthFailure: definitive auth failure, logging out. reason:', error)
      setUser(null)
      setStatus('unauthenticated')
      clearRefreshTimer()
      const code = error instanceof ApiError ? error.code : undefined
      if (code === 'AUTH_ACCOUNT_DISABLED') {
        navigate('/account-disabled', { replace: true })
      } else {
        setSessionExpired(true)
        navigate('/session-expired', { replace: true })
      }
    })
    return () => {
      setRefreshHandler(null)
      setOnAuthFailure(null)
    }
  }, [refreshSession, clearRefreshTimer, navigate])

  // Restore session on app startup via the refresh cookie — never render protected routes before
  // this resolves (see `isInitializing`). Routed through triggerRefresh (rather than calling
  // refreshSession directly) and guarded by a ref so React 18 StrictMode's dev-only double-invoke
  // of this effect can't fire two concurrent /auth/refresh calls with the same cookie.
  useEffect(() => {
    if (startupRestoreStartedRef.current) return
    startupRestoreStartedRef.current = true

    let cancelled = false
    console.info('[auth] init: restoring session on app startup')
    triggerRefresh()
      .then(() => {
        console.info('[auth] init: session restored')
      })
      .catch((err) => {
        console.info('[auth] init: no valid session to restore (expected on first visit):', err instanceof Error ? err.message : err)
      })
      .finally(() => {
        if (!cancelled) setStatus((s) => (s === 'initializing' ? 'unauthenticated' : s))
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Refresh promptly when the tab becomes visible again if we believe we're authenticated —
  // covers the case where the access token expired while the tab was backgrounded. Routed through
  // triggerRefresh so this can never race the proactive-timer or 401-triggered refresh, and
  // throttled so rapid tab-switching can't spam the endpoint.
  useEffect(() => {
    const handler = () => {
      if (document.visibilityState !== 'visible' || status !== 'authenticated') return
      const now = Date.now()
      if (now - lastVisibilityRefreshAtRef.current < MIN_VISIBILITY_REFRESH_INTERVAL_MS) {
        console.info('[auth] visibilitychange: skipping refresh, refreshed recently')
        return
      }
      lastVisibilityRefreshAtRef.current = now
      console.info('[auth] visibilitychange: tab visible again, refreshing session')
      void triggerRefresh().catch(() => {
        /* handled inside refreshSession / onAuthFailure */
      })
    }
    document.addEventListener('visibilitychange', handler)
    return () => document.removeEventListener('visibilitychange', handler)
  }, [status])

  const login = useCallback(async (identifier: string, password: string, rememberMe = false) => {
    console.info('[auth] login: attempting sign-in for', identifier)
    setAuthenticationError(null)
    try {
      const data = await authService.login({ identifier, password, remember_me: rememberMe })
      setAccessToken(data.access_token)
      setUser(data.user)
      setStatus('authenticated')
      setSessionExpired(false)
      scheduleRefresh(data.expires_in)
      console.info('[auth] login: succeeded for', data.user?.username)
    } catch (err) {
      console.warn('[auth] login: failed:', err)
      const message = err instanceof Error ? err.message : 'Sign-in failed. Please try again.'
      setAuthenticationError(message)
      throw err
    }
  }, [scheduleRefresh])

  const register = useCallback(async (payload: { email: string; username: string; full_name: string; password: string }) => {
    setAuthenticationError(null)
    try {
      await authService.register(payload)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed. Please try again.'
      setAuthenticationError(message)
      throw err
    }
  }, [])

  const logout = useCallback(async () => {
    console.info('[auth] logout: reason=user-initiated')
    try {
      await authService.logout()
    } catch {
      /* best-effort — clear local state regardless */
    }
    setAccessToken(null)
    setUser(null)
    setStatus('unauthenticated')
    clearRefreshTimer()
  }, [clearRefreshTimer])

  const logoutAll = useCallback(async () => {
    console.info('[auth] logout: reason=user-initiated-all-devices')
    try {
      await authService.logoutAll()
    } catch {
      /* best-effort */
    }
    setAccessToken(null)
    setUser(null)
    setStatus('unauthenticated')
    clearRefreshTimer()
  }, [clearRefreshTimer])

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    // Backend revokes every session (including this one) on password change — treat as logout.
    await authService.changePassword({ current_password: currentPassword, new_password: newPassword })
    setAccessToken(null)
    setUser(null)
    setStatus('unauthenticated')
    clearRefreshTimer()
  }, [clearRefreshTimer])

  const hasRole = useCallback((role: string) => user?.role === role, [user])
  const hasPermission = useCallback((permission: string) => !!user?.permissions.includes(permission), [user])
  const clearAuthenticationError = useCallback(() => setAuthenticationError(null), [])

  const value = useMemo<AuthContextValue>(() => ({
    status,
    isInitializing: status === 'initializing',
    isAuthenticated: status === 'authenticated',
    user,
    authenticationError,
    sessionExpired,
    login,
    register,
    logout,
    logoutAll,
    refreshSession,
    changePassword,
    hasRole,
    hasPermission,
    clearAuthenticationError,
  }), [status, user, authenticationError, sessionExpired, login, register, logout, logoutAll, refreshSession, changePassword, hasRole, hasPermission, clearAuthenticationError])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
