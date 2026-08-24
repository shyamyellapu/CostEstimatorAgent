// Frontend-only helpers. NEVER used for authorization decisions — only for UI/session timing
// convenience (e.g. showing a "session expiring soon" dialog). The backend is always the source
// of truth for what a token/session is allowed to do.
import { CSRF_COOKIE_NAME } from './auth.constants'

export function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1')}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

export function getCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE_NAME)
}

/** Decodes a JWT payload WITHOUT verifying its signature. UI timing convenience only. */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split('.')
    if (!payload) return null
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=')
    const json = decodeURIComponent(
      atob(padded)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join('')
    )
    return JSON.parse(json)
  } catch {
    return null
  }
}
