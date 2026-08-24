import { useEffect, useState, useCallback } from 'react'
import { Monitor, Smartphone, LogOut, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'
import { authService } from '../services/authService'
import type { SessionOut } from '../services/authService'

export default function ActiveSessionsPage() {
  const [sessions, setSessions] = useState<SessionOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSessions(await authService.listSessions())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function handleRevoke(sessionId: string) {
    if (!window.confirm('Sign out this device?')) return
    try {
      await authService.revokeSession(sessionId)
      toast.success('Session revoked.')
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke session.')
    }
  }

  async function handleRevokeAllOthers() {
    if (!window.confirm('Sign out of all other devices?')) return
    try {
      await authService.revokeAllOtherSessions()
      toast.success('Other sessions signed out.')
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke sessions.')
    }
  }

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '3rem' }}><span className="spinner spinner-lg" /></div>
  }
  if (error) {
    return <div className="empty-state"><h3>Couldn't load sessions</h3><p>{error}</p></div>
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Devices and browsers currently signed in to your account.
        </p>
        <button className="btn btn-secondary btn-sm" onClick={handleRevokeAllOthers}>
          <LogOut size={14} /> Sign out other devices
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {sessions.map((s) => (
          <div key={s.id} className="card" style={{ padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{
              width: 40, height: 40, borderRadius: 'var(--radius-md)', background: 'var(--gray-100)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              {s.device_name?.toLowerCase().includes('mobile') ? <Smartphone size={18} /> : <Monitor size={18} />}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{s.browser || 'Unknown browser'} · {s.operating_system || 'Unknown OS'}</span>
                {s.is_current && <span className="badge badge-success"><ShieldCheck size={11} style={{ marginRight: 3 }} />This device</span>}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                {s.ip_address || 'Unknown IP'} · Signed in {new Date(s.created_at).toLocaleString()}
                {s.last_activity_at && <> · Last active {new Date(s.last_activity_at).toLocaleString()}</>}
              </div>
            </div>
            {!s.is_current && (
              <button className="btn btn-ghost btn-sm" onClick={() => handleRevoke(s.id)}>Revoke</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
