import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, PlusCircle, Scale, ClipboardList,
  FileSpreadsheet, BarChart2, FileText, History, Settings, Zap, X, Calculator, Inbox,
  Users, ShieldCheck, ShieldAlert, FileClock,
} from 'lucide-react'
import { usePermissions } from '../../hooks/usePermissions'
import { PERMISSIONS, ROLES } from '../../auth/auth.constants'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

interface NavItem {
  to: string
  icon: typeof LayoutDashboard
  label: string
  permissions?: string[]
  roles?: string[]
}

interface NavSection {
  label: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    label: 'Main',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', permissions: [PERMISSIONS.DASHBOARD_READ] },
      { to: '/estimate/new', icon: PlusCircle, label: 'New Estimate', permissions: [PERMISSIONS.ESTIMATES_CREATE] },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/drawing-costing', icon: Calculator, label: 'Drawing Costing', permissions: [PERMISSIONS.DRAWINGS_PROCESS] },
      { to: '/weight-calculator', icon: Scale, label: 'Weight Calculator', roles: [ROLES.ESTIMATOR, ROLES.MANAGER, ROLES.ADMIN] },
      { to: '/boq-parser', icon: ClipboardList, label: 'BOQ Parser', permissions: [PERMISSIONS.BOQ_PARSE] },
    ],
  },
  {
    label: 'Output',
    items: [
      { to: '/excel-generator', icon: FileSpreadsheet, label: 'Excel Generator', permissions: [PERMISSIONS.EXCEL_GENERATE] },
      { to: '/quote-summary', icon: BarChart2, label: 'Quote Summary', permissions: [PERMISSIONS.QUOTATIONS_READ] },
      { to: '/cover-letter', icon: FileText, label: 'Cover Letter', permissions: [PERMISSIONS.COVER_LETTERS_GENERATE] },
    ],
  },
  {
    label: 'RFQ Platform',
    items: [
      { to: '/rfq', icon: Inbox, label: 'RFQ Inbox', permissions: [PERMISSIONS.RFQ_READ] },
    ],
  },
  {
    label: 'Admin',
    items: [
      { to: '/history', icon: History, label: 'Job History', permissions: [PERMISSIONS.JOB_HISTORY_READ] },
      { to: '/settings', icon: Settings, label: 'Settings', permissions: [PERMISSIONS.SETTINGS_READ] },
      { to: '/admin/users', icon: Users, label: 'User Management', permissions: [PERMISSIONS.USERS_READ] },
      { to: '/admin/sessions', icon: ShieldAlert, label: 'Session Administration', permissions: [PERMISSIONS.SESSIONS_READ] },
      { to: '/admin/audit-logs', icon: FileClock, label: 'Audit Logs', permissions: [PERMISSIONS.AUDIT_LOGS_READ] },
      { to: '/sessions', icon: ShieldCheck, label: 'Active Sessions' },
    ],
  },
]

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { hasAnyPermission, hasAnyRole } = usePermissions()

  const visibleSections = navSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        if (item.permissions && !hasAnyPermission(item.permissions)) return false
        if (item.roles && !hasAnyRole(item.roles)) return false
        return true
      }),
    }))
    .filter((section) => section.items.length > 0)

  return (
    <aside className={`sidebar${open ? ' open' : ''}`}>
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Zap size={18} strokeWidth={2.5} />
        </div>
        <div className="sidebar-logo-text">
          <h2>CostEstimator</h2>
          <span>AI Agent Platform</span>
        </div>
        {/* Mobile close */}
        <button
          onClick={onClose}
          style={{
            marginLeft: 'auto', display: 'none', background: 'none', border: 'none',
            cursor: 'pointer', color: 'var(--text-muted)', padding: '4px'
          }}
          className="sidebar-close-btn"
          aria-label="Close sidebar"
        >
          <X size={16} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {visibleSections.map((section) => (
          <div key={section.label}>
            <div className="nav-section-label">{section.label}</div>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                onClick={onClose}
              >
                <item.icon className="nav-icon" size={18} />
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>
          Cost Estimator AI
        </div>
        <div>v1.0.0 · MVP Build</div>
      </div>
    </aside>
  )
}

