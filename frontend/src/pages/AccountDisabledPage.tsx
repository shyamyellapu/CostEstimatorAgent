import { Link } from 'react-router-dom'
import { UserX } from 'lucide-react'

export default function AccountDisabledPage() {
  return (
    <div className="auth-status-page">
      <div className="card auth-status-card">
        <div className="auth-status-icon" style={{ background: 'var(--error-50)' }}>
          <UserX size={28} color="var(--error-500)" />
        </div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem' }}>Account disabled</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          Your account has been disabled. Contact your administrator if you believe this is an error.
        </p>
        <Link to="/login" className="btn btn-secondary">Back to sign in</Link>
      </div>
    </div>
  )
}
