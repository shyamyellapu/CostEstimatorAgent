import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ArrowRight, Filter } from 'lucide-react'
import { api } from '../api/client'

const statusConfig: Record<string, { badge: string; label: string }> = {
  draft:                { badge: 'badge-neutral', label: 'Draft' },
  extracting:           { badge: 'badge-warning', label: 'Extracting' },
  pending_confirmation: { badge: 'badge-warning', label: 'Pending Review' },
  calculating:          { badge: 'badge-primary', label: 'Calculating' },
  completed:            { badge: 'badge-success', label: 'Completed' },
  failed:               { badge: 'badge-error',   label: 'Failed' },
}

export default function JobHistory() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    api.get('/history?limit=200')
      .then(r => setJobs(r.data))
      .catch(() => setJobs([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = jobs.filter(j => {
    const q = search.toLowerCase()
    const matchSearch = !q || [j.job_number, j.client_name, j.project_name].some(f => f?.toLowerCase().includes(q))
    const matchStatus = !statusFilter || j.status === statusFilter
    return matchSearch && matchStatus
  })

  return (
    <div className="animate-fade-in">
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Job History</h1>
          <p className="page-subtitle">{jobs.length} total estimation jobs</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/estimate/new')}>+ New Estimate</button>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="card-body" style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
            <Search size={16} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input className="form-input" style={{ paddingLeft: 34 }} placeholder="Search by job #, client, or project…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Filter size={14} style={{ color: 'var(--text-muted)' }} />
            <select className="form-select" style={{ width: 160 }} value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="pending_confirmation">Pending Review</option>
            </select>
          </div>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Showing {filtered.length} of {jobs.length}</span>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem' }}><div className="spinner spinner-lg" style={{ margin: '0 auto' }} /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <h3>No jobs found</h3>
          <p>{search || statusFilter ? 'Try changing your search or filter.' : 'Create your first estimate to get started.'}</p>
          <button className="btn btn-primary" onClick={() => navigate('/estimate/new')}>+ New Estimate</button>
        </div>
      ) : (
        <div className="card">
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job #</th><th>Client</th><th>Project</th><th>Reference</th>
                  <th>Status</th><th className="text-right">Selling Price</th>
                  <th>Created</th><th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(job => {
                  const sc = statusConfig[job.status] || statusConfig.draft
                  return (
                    <tr key={job.id}>
                      <td><span style={{ fontWeight: 700, color: 'var(--primary-700)', fontSize: '0.8rem' }}>{job.job_number}</span></td>
                      <td>{job.client_name || '—'}</td>
                      <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.project_name || '—'}</td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{job.project_ref || '—'}</td>
                      <td><span className={`badge ${sc.badge}`}>{sc.label}</span></td>
                      <td className="text-right">
                        {job.selling_price
                          ? <span style={{ fontWeight: 700, color: 'var(--primary-700)' }}>{job.currency || 'AED'} {job.selling_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                          : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{new Date(job.created_at).toLocaleDateString()}</td>
                      <td>
                        <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/quote-summary/${job.id}`)}>
                          View <ArrowRight size={12} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
