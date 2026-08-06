import { useEffect, useState, useCallback } from 'react'
import { Monitor, Smartphone, LogOut } from 'lucide-react'
import toast from 'react-hot-toast'
import { adminService } from '../services/adminService'
import type { AdminSession } from '../services/adminService'

export default function AdminSessionsPage() {
  const [sessions, setSessions] = useState<AdminSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSessions(await adminService.listAllSessions())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function handleRevoke(sessionId: string) {
    if (!window.confirm('Revoke this session? The user will be signed out immediately.')) return
    try {
      await adminService.revokeSession(sessionId)
      toast.success('Session revoked.')
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke session.')
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
      <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
        All active sessions across every user account.
      </p>
      <div className="card">
        <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th><th>Device</th><th>IP Address</th><th>Created</th><th>Last Active</th><th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 600 }}>{s.user_email || s.user_id}</td>
                  <td>
                    {s.device_name?.toLowerCase().includes('mobile') ? <Smartphone size={14} /> : <Monitor size={14} />}{' '}
                    {s.browser || 'Unknown'} · {s.operating_system || 'Unknown'}
                  </td>
                  <td>{s.ip_address || '—'}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{new Date(s.created_at).toLocaleString()}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {s.last_activity_at ? new Date(s.last_activity_at).toLocaleString() : 'Never'}
                  </td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={() => handleRevoke(s.id)}>
                      <LogOut size={14} /> Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
