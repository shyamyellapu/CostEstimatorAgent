import { Link } from 'react-router-dom'
import { Clock } from 'lucide-react'

export default function SessionExpiredPage() {
  return (
    <div className="auth-status-page">
      <div className="card auth-status-card">
        <div className="auth-status-icon" style={{ background: 'var(--gray-100)' }}>
          <Clock size={28} color="var(--text-secondary)" />
        </div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem' }}>Session expired</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          For your security, you've been signed out. Please sign in again to continue.
        </p>
        <Link to="/login" className="btn btn-primary btn-lg" style={{ justifyContent: 'center' }}>Sign in again</Link>
      </div>
    </div>
  )
}
