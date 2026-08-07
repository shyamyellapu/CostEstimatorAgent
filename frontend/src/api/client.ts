import axios from 'axios'
import type { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { CSRF_HEADER_NAME } from '../auth/auth.constants'
import { getCsrfToken } from '../auth/auth.utils'

// const API_BASE_URL = import.meta.env.VITE_BACKEND_URL
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL||'https://costestimatorbackend-cdckbnh5gkdsfmgr.centralindia-01.azurewebsites.net'

// In dev, go through Vite's `/api` proxy (see vite.config.ts) instead of calling the backend's
// absolute URL directly. The dev backend runs on 127.0.0.1 while the frontend is usually opened
// on localhost — different hostnames are different *sites* to the browser, so a SameSite=Lax
// refresh-token cookie set by an absolute cross-site request is never attached to later XHR/
// fetch calls. It silently vanishes, and every page reload (which only has that cookie to restore
// the session) is forced back to the login page. Going through the same-origin dev proxy keeps
// the cookie same-site regardless of which loopback hostname the browser happens to be on.
const baseURL = import.meta.env.DEV ? '/api' : `${API_BASE_URL}/api`

export const api = axios.create({
  baseURL,
  timeout: 120000,
  // Required so the HttpOnly refresh-token cookie and the readable CSRF cookie are sent/received.
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ─── In-memory access-token store ──────────────────────────────────────────────────────────────
// The access token is NEVER written to localStorage/sessionStorage. AuthProvider is the only
// writer; this module just holds the current value so the request interceptor can attach it.
let currentAccessToken: string | null = null
export function setAccessToken(token: string | null): void {
  currentAccessToken = token
}
export function getAccessToken(): string | null {
  return currentAccessToken
}

// ─── In-memory CSRF-token store ────────────────────────────────────────────────────────────────
// login/refresh echo the CSRF token in the JSON body (see backend LoginResponse.csrf_token)
// because the CSRF cookie itself is scoped to the backend's own host — in production the SPA
// (*.azurestaticapps.net) and API (*.azurewebsites.net) are different registrable domains, so
// document.cookie on the frontend page can never see a cookie the backend's response set. Caching
// the value here instead of reading it back out of document.cookie is what makes CSRF work
// cross-site; auth.utils.ts's cookie-based getCsrfToken() is kept only as a same-origin fallback.
let currentCsrfToken: string | null = null
export function setCsrfToken(token: string | null): void {
  currentCsrfToken = token
}
export function getCsrfTokenFromMemory(): string | null {
  return currentCsrfToken
}

// AuthProvider registers the actual refresh implementation (it also needs to update React state
// and reschedule the silent-refresh timer) — the interceptor only orchestrates single-flight +
// retry-queue behavior around it.
type RefreshHandler = () => Promise<string>
let refreshHandler: RefreshHandler | null = null
export function setRefreshHandler(fn: RefreshHandler | null): void {
  refreshHandler = fn
}

type AuthFailureHandler = (error: unknown) => void
let onAuthFailure: AuthFailureHandler | null = null
export function setOnAuthFailure(fn: AuthFailureHandler | null): void {
  onAuthFailure = fn
}

/** Error subclass carrying the backend's stable machine-readable error code, when available. */
export class ApiError extends Error {
  code?: string
  /** HTTP status code, when the failure came from a server response (undefined for network errors). */
  status?: number
  /** True when the request never reached the server (offline, timeout, DNS, CORS) — never a reason to log out. */
  isNetworkError: boolean
  constructor(message: string, code?: string, status?: number, isNetworkError = false) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.isNetworkError = isNetworkError
  }
}

// Requests to these auth endpoints must never trigger an automatic refresh-and-retry — a 401 from
// login/register/refresh/forgot-password/reset-password is a normal expected response, not an
// expired-session condition.
const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/forgot-password', '/auth/reset-password']

function isPublicAuthRequest(url?: string): boolean {
  if (!url) return false
  return NO_REFRESH_PATHS.some((path) => url.includes(path))
}

const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete'])

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (currentAccessToken) {
    config.headers.set('Authorization', `Bearer ${currentAccessToken}`)
  }
  const method = (config.method || 'get').toLowerCase()
  if (MUTATING_METHODS.has(method)) {
    const csrfToken = getCsrfTokenFromMemory() ?? getCsrfToken()
    if (csrfToken) {
      config.headers.set(CSRF_HEADER_NAME, csrfToken)
    }
  }
  return config
})

// ─── Single-flight refresh, shared by EVERY trigger ────────────────────────────────────────────
// A refresh can be kicked off from several independent places: a 401 response interceptor here,
// AuthProvider's startup session-restore effect, its tab-visibility handler, and its proactive
// pre-expiry timer. If two of those fire within the same few milliseconds (e.g. a React 18
// StrictMode double-effect, or the user switching tabs right as the proactive timer elapses),
// each one presents the SAME refresh-token cookie to the backend. Since refresh tokens rotate
// on every use, the backend treats a second, still-in-flight presentation of an already-rotated
// token as a replay and revokes the whole session — logging the user out for no real reason.
//
// Routing every trigger through this single module-level in-flight promise guarantees at most
// one `/auth/refresh` network call is ever outstanding at a time, regardless of how many places
// asked for one; everyone else just awaits the same promise.
let inFlightRefresh: Promise<string> | null = null

export function triggerRefresh(): Promise<string> {
  if (!refreshHandler) {
    return Promise.reject(new Error('No refresh handler registered'))
  }
  if (!inFlightRefresh) {
    console.info('[auth] triggerRefresh: starting new refresh request')
    inFlightRefresh = refreshHandler().finally(() => {
      inFlightRefresh = null
    })
  } else {
    console.info('[auth] triggerRefresh: reusing in-flight refresh request')
  }
  return inFlightRefresh
}

interface RetryableConfig extends AxiosRequestConfig {
  _retry?: boolean
}

api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const originalRequest = err.config as RetryableConfig | undefined

    const status = err.response?.status
    const canAttemptRefresh =
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isPublicAuthRequest(originalRequest.url) &&
      !!refreshHandler

    if (canAttemptRefresh) {
      originalRequest._retry = true
      console.info('[auth] 401 received for', originalRequest.url, '- attempting refresh + retry')
      try {
        const newToken = await triggerRefresh()
        originalRequest.headers = originalRequest.headers ?? {}
        ;(originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`
        return api(originalRequest)
      } catch (refreshError) {
        console.warn('[auth] refresh failed after 401, logging out:', refreshError)
        setAccessToken(null)
        setCsrfToken(null)
        onAuthFailure?.(refreshError)
        return Promise.reject(refreshError)
      }
    }

    if (!err.response) {
      // Network/timeout/CORS failure — the request never reached the server. Never treat this
      // as an authentication failure.
      return Promise.reject(new ApiError(err.message || 'Network error', undefined, undefined, true))
    }

    type ValidationDetail = { loc?: (string | number)[]; msg?: string }[]
    const errorBody = err.response?.data as
      | { detail?: string | ValidationDetail; error?: { message?: string; code?: string } }
      | undefined

    // FastAPI's default request-validation handler (422) returns `detail` as an array of
    // {loc, msg} objects rather than a string — turn that into a readable message.
    let detailMessage: string | undefined
    if (Array.isArray(errorBody?.detail)) {
      detailMessage = errorBody.detail
        .map((d) => {
          const field = d.loc?.[d.loc.length - 1]
          return field ? `${field}: ${d.msg}` : d.msg
        })
        .filter(Boolean)
        .join('; ')
    } else {
      detailMessage = errorBody?.detail
    }

    const msg = detailMessage ?? errorBody?.error?.message ?? err.message ?? 'An error occurred'
    return Promise.reject(new ApiError(msg, errorBody?.error?.code, err.response?.status, false))
  }
)

