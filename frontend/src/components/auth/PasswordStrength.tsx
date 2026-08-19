import { Check, X } from 'lucide-react'

interface PolicyRule {
  label: string
  test: (password: string) => boolean
}

const RULES: PolicyRule[] = [
  { label: 'At least 8 characters', test: (p) => p.length >= 8 },
  { label: 'One uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { label: 'One lowercase letter', test: (p) => /[a-z]/.test(p) },
  { label: 'One number', test: (p) => /\d/.test(p) },
  { label: 'One special character', test: (p) => /[^\w\s]/.test(p) },
]

function scorePassword(password: string): number {
  return RULES.filter((r) => r.test(password)).length
}

/** Live password-strength meter + policy checklist, matching the backend password policy. */
export default function PasswordStrength({ password }: { password: string }) {
  if (!password) return null

  const score = scorePassword(password)
  const level = score <= 2 ? 'weak' : score <= 4 ? 'fair' : 'strong'
  const label = level === 'weak' ? 'Weak' : level === 'fair' ? 'Fair' : 'Strong'
  const labelColor = level === 'weak' ? 'var(--error-500)' : level === 'fair' ? 'var(--warning-500)' : 'var(--success-600)'

  return (
    <div className="password-strength">
      <div className="password-strength-bars">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className={`password-strength-bar ${i < score ? `filled-${level}` : ''}`} />
        ))}
      </div>
      <span className="password-strength-label" style={{ color: labelColor }}>{label}</span>
      <ul className="password-policy-list">
        {RULES.map((rule) => {
          const met = rule.test(password)
          return (
            <li key={rule.label} className={met ? 'met' : ''}>
              {met ? <Check size={12} /> : <X size={12} />}
              {rule.label}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
