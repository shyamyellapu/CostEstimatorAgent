import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { UserPlus } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import PasswordField from './PasswordField'
import PasswordStrength from './PasswordStrength'

const USERNAME_PATTERN = /^[a-zA-Z0-9_.-]+$/

export default function SignupForm() {
  const { register, authenticationError, clearAuthenticationError } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  function validate(): string | null {
    if (username.length < 3 || !USERNAME_PATTERN.test(username)) {
      return 'Username must be at least 3 characters and contain only letters, numbers, dots, underscores or hyphens.'
    }
    if (password.length < 8) {
      return 'Password must be at least 8 characters.'
    }
    if (password !== confirmPassword) {
      return 'Passwords do not match.'
    }
    return null
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (submitting) return
    clearAuthenticationError()
    const validationError = validate()
    if (validationError) {
      setLocalError(validationError)
      return
    }
    setLocalError(null)
    setSubmitting(true)
    try {
      // requested_role is intentionally not sent — the server always assigns the configured
      // default self-registration role; only an administrator can grant elevated access.
      await register({ email, username, full_name: fullName, password })
      setSuccess(true)
      setTimeout(() => navigate('/login', { replace: true }), 1500)
    } catch {
      // authenticationError is already set by AuthProvider — shown below.
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <div className="auth-error-banner" style={{ background: 'var(--success-50)', borderColor: 'var(--success-100)', color: 'var(--success-600)' }}>
        Account created. Redirecting to sign in…
      </div>
    )
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      {(localError || authenticationError) && (
        <div className="auth-error-banner" role="alert">{localError || authenticationError}</div>
      )}

      <div className="form-group">
        <label className="form-label" htmlFor="signup-name">Full name</label>
        <input
          id="signup-name" className="form-input" type="text" autoComplete="name" autoFocus required
          value={fullName} onChange={(e) => setFullName(e.target.value)}
        />
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="signup-username">Username</label>
        <input
          id="signup-username" className="form-input" type="text" autoComplete="username" required
          value={username} onChange={(e) => setUsername(e.target.value.toLowerCase())}
        />
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="signup-email">Business email</label>
        <input
          id="signup-email" className="form-input" type="email" autoComplete="email" required
          value={email} onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <PasswordField
        label="Password" autoComplete="new-password" required
        value={password} onChange={(e) => setPassword(e.target.value)}
      />
      <PasswordStrength password={password} />

      <PasswordField
        label="Confirm password" autoComplete="new-password" required
        value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
      />

      <button type="submit" className="btn btn-primary btn-lg" disabled={submitting} style={{ justifyContent: 'center' }}>
        {submitting ? <span className="spinner" /> : <UserPlus size={16} />}
        {submitting ? 'Creating account…' : 'Create account'}
      </button>

      <div className="auth-footer-row">
        Already have an account? <Link to="/login" className="auth-link">Sign in</Link>
      </div>
    </form>
  )
}
