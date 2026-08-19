import { AlertTriangle } from 'lucide-react'
import { useSessionTimeout } from '../../hooks/useSessionTimeout'

/** Shown when the refresh token itself is no longer valid (expired/revoked/reuse-detected). */
export default function SessionWarningDialog() {
  const { showWarning, dismiss, retry } = useSessionTimeout()

  if (!showWarning) return null

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      style={{
        position: 'fixed', inset: 0, background: 'rgb(15 23 42 / 0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      }}
    >
      <div className="card" style={{ maxWidth: 380, width: '90%', padding: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <AlertTriangle size={22} color="var(--warning-500)" />
          <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Your session has expired</h3>
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
          For your security, you've been signed out. Please sign in again to continue.
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={dismiss}>Dismiss</button>
          <button className="btn btn-primary" onClick={() => void retry()}>Try again</button>
        </div>
      </div>
    </div>
  )
}
