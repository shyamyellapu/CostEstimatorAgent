import { useLocation } from 'react-router-dom'
import { Menu, Bell, Search } from 'lucide-react'

const routeLabels: Record<string, string> = {
  '/dashboard':        'Dashboard',
  '/estimate/new':     'New Estimate',
  '/drawing-reader':   'Drawing Reader',
  '/weight-calculator':'Weight Calculator',
  '/boq-parser':       'BOQ Parser',
  '/excel-generator':  'Excel Generator',
  '/quote-summary':    'Quote Summary',
  '/cover-letter':     'Cover Letter Generator',
  '/history':          'Job History',
  '/settings':         'Settings',
}

interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { pathname } = useLocation()
  const label = routeLabels[pathname] || routeLabels[`/${pathname.split('/')[1]}`] || 'Cost Estimator'

  return (
    <header className="page-header">
      <button
        className="mobile-menu-btn"
        onClick={onMenuClick}
        aria-label="Open navigation"
        style={{ display: 'flex', marginRight: '0.75rem' }}
      >
        <Menu size={18} />
      </button>

      <div style={{ flex: 1 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.02em' }}>{label}</h1>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {/* Search hint */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.4rem 0.75rem',
          background: 'var(--gray-100)', borderRadius: 'var(--radius-full)',
          color: 'var(--text-muted)', fontSize: '0.8125rem',
          cursor: 'pointer',
        }}>
          <Search size={14} />
          <span style={{ display: 'none' }} className="search-hint">Quick search...</span>
        </div>

        {/* Notification bell */}
        <button
          className="btn btn-ghost btn-icon"
          style={{ position: 'relative' }}
          aria-label="Notifications"
        >
          <Bell size={18} />
          <span style={{
            position: 'absolute', top: 4, right: 4,
            width: 7, height: 7,
            background: 'var(--error-500)',
            borderRadius: '50%',
            border: '1.5px solid white'
          }} />
        </button>

        {/* Avatar */}
        <div style={{
          width: 32, height: 32,
          background: 'linear-gradient(135deg, var(--primary-600), var(--primary-800))',
          borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'white', fontSize: '0.8rem', fontWeight: 700,
          cursor: 'pointer', flexShrink: 0,
        }}>
          CE
        </div>
      </div>
    </header>
  )
}
