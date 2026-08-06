import { useEffect, useState, useCallback } from 'react'
import { ShieldAlert } from 'lucide-react'
import { adminService } from '../services/adminService'
import type { AuditLogEntry } from '../services/adminService'

const statusBadge: Record<string, string> = {
  success: 'badge-success',
  failure: 'badge-error',
}

export default function AdminAuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pageSize = 50

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminService.listAuditLogs({ page, page_size: pageSize })
      setLogs(res.items)
      setTotal(res.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit logs.')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { void load() }, [load])

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '3rem' }}><span className="spinner spinner-lg" /></div>
  }
  if (error) {
    return <div className="empty-state"><h3>Couldn't load audit logs</h3><p>{error}</p></div>
  }

  return (
    <div>
      <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
        Immutable authentication and authorization audit trail.
      </p>
      <div className="card">
        <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th><th>Action</th><th>Status</th><th>User</th><th>IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={5}>
                  <div className="empty-state">
                    <div className="empty-state-icon"><ShieldAlert size={28} /></div>
                    <h3>No audit events</h3>
                  </div>
                </td></tr>
              ) : logs.map((l) => (
                <tr key={l.id}>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{new Date(l.timestamp).toLocaleString()}</td>
                  <td>{l.action}</td>
                  <td><span className={`badge ${statusBadge[l.status] ?? 'badge-neutral'}`}>{l.status}</span></td>
                  <td style={{ fontSize: '0.8rem' }}>{l.user_id || '—'}</td>
                  <td style={{ fontSize: '0.8rem' }}>{l.ip_address || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Page {page} of {Math.max(1, Math.ceil(total / pageSize))}</span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <button className="btn btn-secondary btn-sm" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
      </div>
    </div>
  )
}
