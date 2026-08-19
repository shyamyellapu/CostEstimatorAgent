import { useCallback, useState } from 'react'
import { useAuth } from './useAuth'

/**
 * Surfaces the `sessionExpired` flag from AuthProvider as a dismissible warning, and exposes a
 * way to attempt re-authentication (used by SessionWarningDialog). Access-token refresh already
 * happens silently in the background; this only fires when the refresh token itself is no longer
 * valid (expired, revoked, or reuse-detected).
 */
export function useSessionTimeout() {
  const { sessionExpired, refreshSession } = useAuth()
  const [dismissed, setDismissed] = useState(false)

  const dismiss = useCallback(() => setDismissed(true), [])

  const retry = useCallback(async () => {
    try {
      await refreshSession()
      setDismissed(false)
      return true
    } catch {
      return false
    }
  }, [refreshSession])

  return {
    showWarning: sessionExpired && !dismissed,
    dismiss,
    retry,
  }
}
