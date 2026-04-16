import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, TrendingUp, Package, DollarSign, Clock, Plus, ArrowRight, CheckCircle, AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface Job {
  id: string
  job_number: string
  client_name: string
  project_name: string
  status: string
  selling_price: number
  currency: string
  created_at: string
}

const statusConfig: Record<string, { badge: string; label: string }> = {
  draft:                { badge: 'badge-neutral', label: 'Draft' },
  extracting:           { badge: 'badge-warning', label: 'Extracting' },
  pending_confirmation: { badge: 'badge-warning', label: 'Pending Review' },
  calculating:          { badge: 'badge-primary', label: 'Calculating' },
  completed:            { badge: 'badge-success', label: 'Completed' },
  failed:               { badge: 'badge-error',   label: 'Failed' },
}

const mockChartData = [
  { month: 'Nov', value: 245000 },
  { month: 'Dec', value: 318000 },
  { month: 'Jan', value: 289000 },
  { month: 'Feb', value: 412000 },
  { month: 'Mar', value: 375000 },
  { month: 'Apr', value: 498000 },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/estimate/jobs?limit=10')
      .then(r => setJobs(r.data))
      .catch(() => setJobs([]))
      .finally(() => setLoading(false))
  }, [])

  const completed = jobs.filter(j => j.status === 'completed')
  const totalRevenue = completed.reduce((s, j) => s + (j.selling_price || 0), 0)
  const pending = jobs.filter(j => j.status === 'pending_confirmation').length

  return (
    <div className="animate-fade-in">
      {/* Page title */}
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Welcome back — here's your estimation overview</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/estimate/new')}>
          <Plus size={16} /> New Estimate
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard
          icon={<Package size={20} />}
          iconBg="var(--primary-100)"
          iconColor="var(--primary-600)"
          value={jobs.length}
          label="Total Jobs"
          accent={['#3b82f6', '#60a5fa']}
        />
        <StatCard
          icon={<CheckCircle size={20} />}
          iconBg="var(--success-100)"
          iconColor="var(--success-600)"
          value={completed.length}
          label="Completed"
          accent={['#22c55e', '#4ade80']}
        />
        <StatCard
          icon={<DollarSign size={20} />}
          iconBg="#fef9c3"
          iconColor="#ca8a04"
          value={`AED ${(totalRevenue / 1000).toFixed(0)}K`}
          label="Total Quoted"
          accent={['#f59e0b', '#fbbf24']}
        />
        <StatCard
          icon={<AlertCircle size={20} />}
          iconBg="#fee2e2"
          iconColor="#dc2626"
          value={pending}
          label="Pending Review"
          accent={['#ef4444', '#f87171']}
        />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Chart */}
        <div className="card" style={{ gridColumn: 'span 2' }}>
          <div className="card-header">
            <div>
              <div className="card-title">Quotation Trend</div>
              <div className="card-subtitle">Monthly quoted value (AED)</div>
            </div>
            <span className="badge badge-success badge-dot">Live</span>
          </div>
          <div className="card-body" style={{ paddingTop: '0.75rem' }}>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={mockChartData}>
                <defs>
                  <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--gray-100)" />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}K`} />
                <Tooltip formatter={(v: number) => [`AED ${v.toLocaleString()}`, 'Quoted']}
                  contentStyle={{ borderRadius: 8, border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)', fontSize: 13 }} />
                <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2.5}
                  fill="url(#areaGrad)" dot={{ r: 4, fill: '#3b82f6', strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Quick Actions</div>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.75rem' }}>
            {[
              { label: 'New Estimate', sub: 'Upload drawings & BOQ', to: '/estimate/new', icon: Plus, color: '#3b82f6', bg: 'var(--primary-50)' },
              { label: 'Drawing Reader', sub: 'Extract from drawings', to: '/drawing-reader', icon: Package, color: '#8b5cf6', bg: '#f5f3ff' },
              { label: 'BOQ Parser', sub: 'Parse BOQ document', to: '/boq-parser', icon: TrendingUp, color: '#10b981', bg: 'var(--success-50)' },
              { label: 'Cover Letter', sub: 'Generate from quotation', to: '/cover-letter', icon: Clock, color: '#f59e0b', bg: 'var(--warning-50)' },
            ].map(a => (
              <button
                key={a.to}
                className="btn btn-ghost"
                onClick={() => navigate(a.to)}
                style={{
                  justifyContent: 'space-between', padding: '0.75rem',
                  background: a.bg, borderRadius: 'var(--radius-md)',
                  border: 'none', textAlign: 'left',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                  <a.icon size={16} color={a.color} />
                  <div>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-primary)' }}>{a.label}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{a.sub}</div>
                  </div>
                </div>
                <ArrowRight size={14} color="var(--text-muted)" />
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Jobs */}
      <div className="card mt-6">
        <div className="card-header">
          <div>
            <div className="card-title">Recent Jobs</div>
            <div className="card-subtitle">Latest estimation jobs</div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/history')}>
            View All <ArrowRight size={14} />
          </button>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              <div className="spinner" style={{ margin: '0 auto' }} />
            </div>
          ) : jobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <h3>No jobs yet</h3>
              <p>Create your first cost estimate to get started.</p>
              <button className="btn btn-primary" onClick={() => navigate('/estimate/new')}>
                <Plus size={16} /> New Estimate
              </button>
            </div>
          ) : (
            <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Job #</th>
                    <th>Client</th>
                    <th>Project</th>
                    <th>Status</th>
                    <th className="text-right">Selling Price</th>
                    <th>Date</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.slice(0, 8).map(job => {
                    const sc = statusConfig[job.status] || statusConfig.draft
                    return (
                      <tr key={job.id}>
                        <td><span style={{ fontWeight: 700, color: 'var(--primary-700)', fontSize: '0.8rem' }}>{job.job_number}</span></td>
                        <td>{job.client_name || '—'}</td>
                        <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.project_name || '—'}</td>
                        <td><span className={`badge ${sc.badge}`}>{sc.label}</span></td>
                        <td className="text-right">
                          {job.selling_price ? `${job.currency || 'AED'} ${job.selling_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
                        </td>
                        <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{new Date(job.created_at).toLocaleDateString()}</td>
                        <td>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => navigate(`/quote-summary/${job.id}`)}
                          >
                            View <ArrowRight size={12} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, iconBg, iconColor, value, label, accent }: any) {
  return (
    <div className="stat-card" style={{ '--accent-from': accent[0], '--accent-to': accent[1] } as any}>
      <div className="stat-icon" style={{ background: iconBg, color: iconColor }}>{icon}</div>
      <div className="stat-content">
        <div className="stat-number">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  )
}
