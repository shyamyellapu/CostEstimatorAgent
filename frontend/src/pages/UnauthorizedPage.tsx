import { Link, useNavigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'

export default function UnauthorizedPage() {
  const navigate = useNavigate()
  return (
    <div className="auth-status-page">
      <div className="card auth-status-card">
        <div className="auth-status-icon" style={{ background: 'var(--warning-50)' }}>
          <ShieldAlert size={28} color="var(--warning-500)" />
        </div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem' }}>Access denied</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          You don't have permission to view this page. If you believe this is a mistake, contact
          your administrator.
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
          <button className="btn btn-secondary" onClick={() => navigate(-1)}>Go back</button>
          <Link to="/dashboard" className="btn btn-primary">Return to dashboard</Link>
        </div>
      </div>
    </div>
  )
}
