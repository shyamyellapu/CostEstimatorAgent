import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { KeyRound } from 'lucide-react'
import AuthLayout from '../components/auth/AuthLayout'
import PasswordField from '../components/auth/PasswordField'
import PasswordStrength from '../components/auth/PasswordStrength'
import { authService } from '../services/authService'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') || ''

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (submitting) return
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await authService.resetPassword({ token, new_password: password })
      navigate('/login', { replace: true, state: { resetSuccess: true } })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'This reset link is invalid or has expired.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!token) {
    return (
      <AuthLayout title="Invalid reset link" subtitle="This password reset link is missing its token.">
        <div className="auth-error-banner">Please request a new password reset link.</div>
        <div className="auth-footer-row">
          <Link to="/forgot-password" className="auth-link">Request a new link</Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Reset your password" subtitle="Choose a new password for your account.">
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {error && <div className="auth-error-banner" role="alert">{error}</div>}
        <PasswordField
          label="New password" autoComplete="new-password" required autoFocus
          value={password} onChange={(e) => setPassword(e.target.value)}
        />
        <PasswordStrength password={password} />
        <PasswordField
          label="Confirm new password" autoComplete="new-password" required
          value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
        />
        <button type="submit" className="btn btn-primary btn-lg" disabled={submitting} style={{ justifyContent: 'center' }}>
          {submitting ? <span className="spinner" /> : <KeyRound size={16} />}
          {submitting ? 'Resetting…' : 'Reset password'}
        </button>
      </form>
    </AuthLayout>
  )
}
