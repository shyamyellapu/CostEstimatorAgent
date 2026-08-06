import type { ReactNode } from 'react'
import { Zap } from 'lucide-react'

interface AuthLayoutProps {
  children: ReactNode
  title: string
  subtitle: string
}

const FEATURES = [
  'AI-powered drawing extraction & costing',
  'Automated BOQ parsing and validation',
  'Quotation, Excel & cover-letter generation',
]

/** Split-screen layout shared by all authentication pages (sign-in, sign-up, password reset...). */
export default function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  return (
    <div className="auth-page">
      <aside className="auth-brand-panel">
        <div className="auth-brand-logo">
          <div className="auth-brand-logo-icon">
            <Zap size={20} strokeWidth={2.5} />
          </div>
          <div className="auth-brand-logo-text">
            <h2>CostEstimator</h2>
            <span>AI Agent Platform</span>
          </div>
        </div>

        <div className="auth-brand-message">
          <h1>Secure access to AI-powered costing, BOQ processing and quotation workflows.</h1>
          <p>
            One workspace for drawing extraction, structural costing, BOQ parsing and quotation
            generation — built for fabrication and EPC estimating teams.
          </p>
          <ul className="auth-brand-features">
            {FEATURES.map((f) => (
              <li key={f}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'white', flexShrink: 0 }} />
                {f}
              </li>
            ))}
          </ul>
        </div>

        <div className="auth-brand-footer">© {new Date().getFullYear()} Cost Estimator AI Agent</div>
      </aside>

      <main className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="auth-mobile-logo">
            <div className="sidebar-logo-icon">
              <Zap size={18} strokeWidth={2.5} />
            </div>
            <div className="sidebar-logo-text">
              <h2>CostEstimator</h2>
              <span>AI Agent Platform</span>
            </div>
          </div>

          <div className="auth-heading">
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>

          {children}
        </div>
      </main>
    </div>
  )
}
