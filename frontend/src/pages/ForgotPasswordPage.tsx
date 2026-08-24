import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Mail } from 'lucide-react'
import AuthLayout from '../components/auth/AuthLayout'
import { authService } from '../services/authService'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      const res = await authService.forgotPassword(email)
      // Always a generic message — never reveals whether the account exists.
      setMessage(res.message)
    } catch {
      setMessage('If an account exists for that email, password reset instructions have been sent.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout title="Forgot your password?" subtitle="Enter your email and we'll send you reset instructions.">
      {message ? (
        <div className="auth-error-banner" style={{ background: 'var(--success-50)', borderColor: 'var(--success-100)', color: 'var(--success-600)' }}>
          {message}
        </div>
      ) : (
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="forgot-email">Email address</label>
            <input
              id="forgot-email" className="form-input" type="email" autoComplete="email" autoFocus required
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary btn-lg" disabled={submitting} style={{ justifyContent: 'center' }}>
            {submitting ? <span className="spinner" /> : <Mail size={16} />}
            {submitting ? 'Sending…' : 'Send reset instructions'}
          </button>
        </form>
      )}
      <div className="auth-footer-row">
        Remembered your password? <Link to="/login" className="auth-link">Sign in</Link>
      </div>
    </AuthLayout>
  )
}
