import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, PlusCircle, FileSearch, Scale, ClipboardList,
  FileSpreadsheet, BarChart2, FileText, History, Settings, Zap, X
} from 'lucide-react'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

const navSections = [
  {
    label: 'Main',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/estimate/new', icon: PlusCircle, label: 'New Estimate' },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/drawing-reader', icon: FileSearch, label: 'Drawing Reader' },
      { to: '/weight-calculator', icon: Scale, label: 'Weight Calculator' },
      { to: '/boq-parser', icon: ClipboardList, label: 'BOQ Parser' },
    ],
  },
  {
    label: 'Output',
    items: [
      { to: '/excel-generator', icon: FileSpreadsheet, label: 'Excel Generator' },
      { to: '/quote-summary', icon: BarChart2, label: 'Quote Summary' },
      { to: '/cover-letter', icon: FileText, label: 'Cover Letter' },
    ],
  },
  {
    label: 'Admin',
    items: [
      { to: '/history', icon: History, label: 'Job History' },
      { to: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
]

export default function Sidebar({ open, onClose }: SidebarProps) {
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
        {navSections.map((section) => (
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
