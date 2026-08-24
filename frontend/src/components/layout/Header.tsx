import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Menu, Bell, Search, LogOut, User as UserIcon } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

const routeLabels: Record<string, string> = {
  '/dashboard':        'Dashboard',
  '/estimate/new':     'New Estimate',
  '/weight-calculator':'Weight Calculator',
  '/boq-parser':       'BOQ Parser',
  '/excel-generator':  'Excel Generator',
  '/quote-summary':    'Quote Summary',
  '/cover-letter':     'Cover Letter Generator',
  '/history':          'Job History',
  '/settings':         'Settings',
  '/admin/users':      'User Management',
  '/sessions':         'Active Sessions',
}

interface HeaderProps {
  onMenuClick: () => void
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || 'U'
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const label = routeLabels[pathname] || routeLabels[`/${pathname.split('/')[1]}`] || 'Cost Estimator'

  async function handleLogout() {
    setMenuOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

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

        {/* User menu */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Account menu"
            style={{
              width: 32, height: 32,
              background: 'linear-gradient(135deg, var(--primary-600), var(--primary-800))',
              borderRadius: '50%', border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'white', fontSize: '0.8rem', fontWeight: 700,
              cursor: 'pointer', flexShrink: 0,
            }}
          >
            {user ? initials(user.full_name) : <UserIcon size={14} />}
          </button>

          {menuOpen && (
            <>
              <div
                onClick={() => setMenuOpen(false)}
                style={{ position: 'fixed', inset: 0, zIndex: 40 }}
              />
              <div
                className="card"
                style={{
                  position: 'absolute', right: 0, top: '2.5rem', width: 220, zIndex: 50,
                  padding: '0.5rem', boxShadow: 'var(--shadow-lg)',
                }}
              >
                {user && (
                  <div style={{ padding: '0.5rem 0.625rem', borderBottom: '1px solid var(--border)', marginBottom: '0.25rem' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>{user.full_name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{user.email}</div>
                    <span className="badge badge-primary" style={{ marginTop: 4 }}>{user.role}</span>
                  </div>
                )}
                <button
                  className="nav-item" style={{ width: '100%' }}
                  onClick={() => { setMenuOpen(false); navigate('/sessions') }}
                >
                  Active Sessions
                </button>
                <button className="nav-item" style={{ width: '100%', color: 'var(--error-600)' }} onClick={handleLogout}>
                  <LogOut size={16} className="nav-icon" /> Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

