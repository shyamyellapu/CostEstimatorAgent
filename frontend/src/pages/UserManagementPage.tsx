import { useEffect, useState, useCallback } from 'react'
import { Users, Search, ShieldCheck, ShieldOff, RotateCcw } from 'lucide-react'
import toast from 'react-hot-toast'
import { adminService } from '../services/adminService'
import type { AdminUser, RoleOut } from '../services/adminService'
import { useAuth } from '../hooks/useAuth'
import { usePermissions } from '../hooks/usePermissions'
import { PERMISSIONS } from '../auth/auth.constants'

const roleBadge: Record<string, string> = {
  admin: 'badge-primary',
  manager: 'badge-info',
  estimator: 'badge-success',
  user: 'badge-neutral',
}

export default function UserManagementPage() {
  const { user: currentUser } = useAuth()
  const { hasPermission } = usePermissions()
  const canAssignRole = hasPermission(PERMISSIONS.USERS_ASSIGN_ROLE)
  const canDisable = hasPermission(PERMISSIONS.USERS_DISABLE)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pageSize = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [userRes, roleRes] = await Promise.all([
        adminService.listUsers({
          search: search || undefined,
          role: roleFilter || undefined,
          is_active: statusFilter ? statusFilter === 'active' : undefined,
          page,
          page_size: pageSize,
        }),
        roles.length ? Promise.resolve(roles) : adminService.listRoles(),
      ])
      setUsers(userRes.items)
      setTotal(userRes.total)
      if (!roles.length) setRoles(roleRes as RoleOut[])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, roleFilter, statusFilter, page])

  useEffect(() => { void load() }, [load])

  async function handleRoleChange(userId: string, role: string) {
    try {
      await adminService.assignRole(userId, role)
      toast.success('Role updated.')
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update role.')
    }
  }

  async function handleStatusToggle(u: AdminUser) {
    const nextActive = !u.is_active
    if (!nextActive && !window.confirm(`Disable ${u.full_name}? They will be signed out of every session immediately.`)) return
    try {
      await adminService.setStatus(u.id, nextActive)
      toast.success(nextActive ? 'User activated.' : 'User disabled.')
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update status.')
    }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="card-body" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: '1 1 220px' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              className="form-input" style={{ paddingLeft: '2rem' }} placeholder="Search name, email or username…"
              value={search} onChange={(e) => { setPage(1); setSearch(e.target.value) }}
            />
          </div>
          <select className="form-select" value={roleFilter} onChange={(e) => { setPage(1); setRoleFilter(e.target.value) }}>
            <option value="">All roles</option>
            {roles.map((r) => <option key={r.id} value={r.name}>{r.name}</option>)}
          </select>
          <select className="form-select" value={statusFilter} onChange={(e) => { setPage(1); setStatusFilter(e.target.value) }}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </select>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{total} user{total === 1 ? '' : 's'}</span>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem' }}><span className="spinner spinner-lg" /></div>
      ) : error ? (
        <div className="empty-state"><h3>Couldn't load users</h3><p>{error}</p></div>
      ) : users.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Users size={28} /></div>
          <h3>No users found</h3>
          <p>Try changing your search or filters.</p>
        </div>
      ) : (
        <div className="card">
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>User</th><th>Email</th><th>Role</th><th>Status</th>
                  <th>Last Login</th><th>Created</th><th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>{u.full_name}<div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>@{u.username}</div></td>
                    <td>{u.email}</td>
                    <td>
                      {canAssignRole ? (
                        <select
                          className="form-select" style={{ fontSize: '0.8125rem', padding: '0.25rem 0.5rem' }}
                          value={u.role ?? ''} onChange={(e) => handleRoleChange(u.id, e.target.value)}
                          disabled={u.id === currentUser?.id}
                        >
                          {roles.map((r) => <option key={r.id} value={r.name}>{r.name}</option>)}
                        </select>
                      ) : (
                        <span>{u.role ?? '—'}</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${u.is_active ? 'badge-success' : 'badge-error'}`}>{u.is_active ? 'Active' : 'Disabled'}</span>
                      {u.role && <span className={`badge ${roleBadge[u.role] ?? 'badge-neutral'}`} style={{ marginLeft: 6 }}>{u.role}</span>}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{new Date(u.created_at).toLocaleDateString()}</td>
                    <td>
                      {canDisable && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => handleStatusToggle(u)}
                          disabled={u.id === currentUser?.id}
                          title={u.id === currentUser?.id ? "You can't disable your own account" : undefined}
                        >
                          {u.is_active ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
                          {u.is_active ? 'Disable' : 'Activate'}
                        </button>
                      )}
                    </td>
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
              <button className="btn btn-ghost btn-sm" onClick={() => void load()}><RotateCcw size={14} /></button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
