import { useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import { LogIn } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import PasswordField from './PasswordField'

interface LocationState {
  from?: { pathname: string }
}

export default function LoginForm() {
  const { login, authenticationError, clearAuthenticationError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const redirectTo = (location.state as LocationState | null)?.from?.pathname || '/dashboard'

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (submitting) return
    clearAuthenticationError()
    setSubmitting(true)
    try {
      await login(identifier, password, rememberMe)
      navigate(redirectTo, { replace: true })
    } catch {
      // authenticationError is already set by AuthProvider — shown below.
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      {authenticationError && (
        <div className="auth-error-banner" role="alert">
          {authenticationError}
        </div>
      )}

      <div className="form-group">
        <label className="form-label" htmlFor="login-identifier">Email or username</label>
        <input
          id="login-identifier"
          className="form-input"
          type="text"
          autoComplete="username"
          autoFocus
          required
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
        />
      </div>

      <PasswordField
        label="Password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <div className="auth-remember-row">
        <label className="auth-checkbox-label">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          Remember this device
        </label>
        <Link to="/forgot-password" className="auth-link">Forgot password?</Link>
      </div>

      <button type="submit" className="btn btn-primary btn-lg" disabled={submitting} style={{ justifyContent: 'center' }}>
        {submitting ? <span className="spinner" /> : <LogIn size={16} />}
        {submitting ? 'Signing in…' : 'Sign in'}
      </button>

      <div className="auth-footer-row">
        Don&apos;t have an account? <Link to="/signup" className="auth-link">Create one</Link>
      </div>
    </form>
  )
}
