import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Inbox, RefreshCw, Plus, Mail, Paperclip, Clock,
  AlertCircle, CheckCircle, Search, Wifi, WifiOff,
  LogIn, Trash2, ChevronRight, MailOpen, ExternalLink, X,
} from 'lucide-react'
import { api } from '../api/client'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Mailbox {
  id: string
  email_address: string
  display_name: string
  is_active: boolean
  last_synced: string | null
  created_at: string
}

interface RFQEmail {
  id: string
  subject: string
  sender_email: string
  sender_name: string
  received_at: string | null
  email_type: string
  rfq_id: string | null
  is_processed: boolean
  attachment_count: number
  mailbox_email: string
  body_text?: string
}

interface RFQRecord {
  id: string
  rfq_number: string
  client_name: string | null
  project_name: string | null
  status: string
  priority: string
  created_at: string
  attachment_count: number
  line_item_count: number
  source: string
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const REDIRECT_URI = `${window.location.origin}/gmail/callback`

const statusBadge: Record<string, string> = {
  received: 'badge-neutral', classifying: 'badge-warning', extracting: 'badge-warning',
  review: 'badge-primary', validated: 'badge-success', costing: 'badge-primary',
  quoted: 'badge-success', closed: 'badge-neutral', rejected: 'badge-error',
}

const priorityColor: Record<string, string> = {
  urgent: '#ef4444', high: '#f59e0b', normal: '#3b82f6', low: '#6b7280',
}

const emailTypeBadge: Record<string, string> = {
  rfq: 'badge-primary', revision: 'badge-warning', clarification: 'badge-neutral', other: 'badge-neutral',
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function emailTypeColor(type: string) {
  return { rfq: '#6366f1', revision: '#f59e0b', clarification: '#3b82f6', other: '#6b7280' }[type] || '#6b7280'
}

function formatRelativeDate(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`
  return d.toLocaleDateString()
}


export default function RFQInbox() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<'rfqs' | 'emails'>('rfqs')
  const [rfqs, setRfqs] = useState<RFQRecord[]>([])
  const [emails, setEmails] = useState<RFQEmail[]>([])
  const [emailsLoading, setEmailsLoading] = useState(false)
  const [stats, setStats] = useState<Record<string, number>>({})
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<string | 'all' | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [emailTypeFilter, setEmailTypeFilter] = useState('')
  const [mailboxFilter, setMailboxFilter] = useState('')
  const [selectedEmail, setSelectedEmail] = useState<RFQEmail | null>(null)
  const [needsReauth, setNeedsReauth] = useState<string[]>([]) // mailbox emails that need re-auth

  const loadMailboxes = useCallback(async () => {
    try { setMailboxes((await api.get('/gmail/mailboxes')).data) } catch {/* handled */}
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [rfqRes, statsRes] = await Promise.all([
        api.get('/rfq', { params: { limit: 100 } }),
        api.get('/rfq/stats'),
      ])
      setRfqs(rfqRes.data)
      setStats(statsRes.data.by_status || {})
    } catch {/* handled */}
    setLoading(false)
  }, [])

  const loadEmails = useCallback(async () => {
    setEmailsLoading(true)
    try { setEmails((await api.get('/gmail/inbox', { params: { limit: 20 } })).data) } catch {/* handled */}
    setEmailsLoading(false)
  }, [])

  useEffect(() => { loadData(); loadMailboxes() }, [loadData, loadMailboxes])
  useEffect(() => { if (tab === 'emails') loadEmails() }, [tab, loadEmails])

  // Listen for OAuth popup completion via localStorage
  // (postMessage is blocked by Google's Cross-Origin-Opener-Policy header)
  // Auto-sync immediately on connect so emails appear without manual action
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === 'gmail-oauth-success') {
        localStorage.removeItem('gmail-oauth-success')
        setNeedsReauth([]) // fresh token — clear any re-auth warnings
        loadMailboxes().then(() => syncMailbox('all'))
      }
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const syncMailbox = async (mbId: string | 'all') => {
    setSyncing(mbId)
    try {
      const body = mbId === 'all' ? { max_messages: 20 } : { mailbox_id: mbId, max_messages: 20 }
      const res = await api.post('/gmail/sync', body)
      if (res.data?.counters?.needs_reauth) {
        // Token has wrong scope — mark affected mailboxes so banner shows
        const affected = mailboxes.filter(m => m.is_active).map(m => m.email_address)
        setNeedsReauth(affected)
      }
      await Promise.all([loadMailboxes(), loadEmails()])
      setTab('emails')
    } catch {/* handled */}
    setSyncing(null)
  }

  const filteredRfqs = rfqs.filter(r => {
    const ok = !search ||
      (r.rfq_number || '').toLowerCase().includes(search.toLowerCase()) ||
      (r.client_name || '').toLowerCase().includes(search.toLowerCase()) ||
      (r.project_name || '').toLowerCase().includes(search.toLowerCase())
    return ok && (!statusFilter || r.status === statusFilter)
  })

  const filteredEmails = emails.filter(e => {
    const ok = !search ||
      (e.subject || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.sender_email || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.sender_name || '').toLowerCase().includes(search.toLowerCase())
    return ok
      && (!emailTypeFilter || e.email_type === emailTypeFilter)
      && (!mailboxFilter || e.mailbox_email === mailboxFilter)
  })

  const totalRfqs = Object.values(stats).reduce((a, b) => a + b, 0)
  const pendingReview = (stats['review'] || 0) + (stats['extracting'] || 0)
  const unprocessedEmails = emails.filter(e => !e.is_processed).length
  const activeMailboxes = mailboxes.filter(m => m.is_active)

  return (
    <div className="animate-fade-in">
      <div className="page-title-bar">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Inbox size={22} /> RFQ Inbox
          </h1>
          <p className="page-subtitle">AI-assisted RFQ intake, classification, and extraction pipeline</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" onClick={() => syncMailbox('all')} disabled={syncing !== null || activeMailboxes.length === 0}>
            <RefreshCw size={14} className={syncing ? 'spin' : ''} />
            {syncing ? 'Syncing…' : 'Sync All'}
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/rfq/new')}>
            <Plus size={14} /> New RFQ
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4" style={{ marginBottom: 20 }}>
        {[
          { label: 'Total RFQs',     value: totalRfqs,              color: '#3b82f6' },
          { label: 'Pending Review', value: pendingReview,          color: '#f59e0b' },
          { label: 'Validated',      value: stats['validated'] || 0, color: '#22c55e' },
          { label: 'Unread Emails',  value: unprocessedEmails,      color: '#8b5cf6' },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Re-auth banner */}
      {needsReauth.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: '#fef3c7', border: '1px solid #fbbf24', borderRadius: 10, marginBottom: 16, fontSize: 13 }}>
          <AlertCircle size={16} color="#d97706" style={{ flexShrink: 0 }} />
          <span style={{ flex: 1, color: '#92400e' }}>
            <strong>Gmail re-authentication required</strong> — the stored token has insufficient permissions (was granted with a restricted scope).
            Click <strong>Re-auth</strong> on the mailbox card below to grant full access.
          </span>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#92400e', padding: 2 }} onClick={() => setNeedsReauth([])}><X size={14} /></button>
        </div>
      )}

      {/* Gmail Connection Section */}
      <GmailSection
        mailboxes={mailboxes}
        syncing={syncing}
        onSync={syncMailbox}
        onDisconnect={async id => { await api.delete(`/gmail/mailboxes/${id}`); loadMailboxes() }}
        onConnected={() => { loadMailboxes(); syncMailbox('all') }}
      />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid var(--border)', marginTop: 20 }}>
        {(['rfqs', 'emails'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 20px', background: 'none', border: 'none',
            borderBottom: tab === t ? '2px solid var(--primary-600)' : '2px solid transparent',
            color: tab === t ? 'var(--primary-600)' : 'var(--text-muted)',
            fontWeight: tab === t ? 600 : 400, cursor: 'pointer', fontSize: 14, marginBottom: -1,
          }}>
            {t === 'rfqs'
              ? `RFQ Pipeline (${totalRfqs})`
              : `Email Inbox (${emails.length}${unprocessedEmails > 0 ? ` · ${unprocessedEmails} new` : ''})`}
          </button>
        ))}
      </div>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder={tab === 'rfqs' ? 'Search RFQs…' : 'Search emails…'}
            className="form-input" style={{ paddingLeft: 32, width: '100%' }} />
        </div>
        {tab === 'rfqs' ? (
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="form-input" style={{ width: 'auto' }}>
            <option value="">All Statuses</option>
            {['received','classifying','extracting','review','validated','costing','quoted','closed'].map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        ) : (
          <>
            <select value={mailboxFilter} onChange={e => setMailboxFilter(e.target.value)} className="form-input" style={{ width: 'auto' }}>
              <option value="">All Mailboxes ({emails.length})</option>
              {mailboxes.filter(m => m.is_active).map(m => {
                const cnt = emails.filter(e => e.mailbox_email === m.email_address).length
                return <option key={m.id} value={m.email_address}>{m.email_address} ({cnt})</option>
              })}
            </select>
            <select value={emailTypeFilter} onChange={e => setEmailTypeFilter(e.target.value)} className="form-input" style={{ width: 'auto' }}>
              <option value="">All Types</option>
              {['rfq','revision','clarification','other'].map(s => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)} ({emails.filter(e => e.email_type === s).length})</option>
              ))}
            </select>
          </>
        )}
      </div>

      {loading ? (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading…</div>
      ) : tab === 'rfqs' ? (
        <RFQTable rfqs={filteredRfqs} onSelect={id => navigate(`/rfq/${id}`)} />
      ) : (
        <EmailPanel
          emails={filteredEmails}
          allEmails={emails}
          selected={selectedEmail}
          loading={emailsLoading || syncing === 'all'}
          onSelect={setSelectedEmail}
          onProcess={async id => { await api.post(`/gmail/inbox/${id}/process`); await loadEmails(); setSelectedEmail(null) }}
          onNavigate={rfqId => navigate(`/rfq/${rfqId}`)}
          onSync={() => syncMailbox('all')}
          syncing={!!syncing}
        />
      )}
    </div>
  )
}

// ─── Gmail Connection Section ─────────────────────────────────────────────────

function GmailSection({ mailboxes, syncing, onSync, onDisconnect, onConnected }: {
  mailboxes: Mailbox[]
  syncing: string | 'all' | null
  onSync: (id: string | 'all') => void
  onDisconnect: (id: string) => void
  onConnected: () => void
}) {
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState('')

  const connectGmail = async () => {
    setConnecting(true)
    setError('')
    console.log("The function is working")
    try {
      console.log("The function is working")
      const res = await api.get('/gmail/auth-url', { params: { redirect_uri: REDIRECT_URI } })
      const popup = window.open(res.data.auth_url, 'gmail-oauth', 'width=520,height=640,left=200,top=100')
      if (!popup) { setError('Popup was blocked. Allow popups for this site and try again.'); setConnecting(false); return }
      const poll = setInterval(() => {
        try {
          // popup.closed throws under Google's Cross-Origin-Opener-Policy — catch silently
          if (popup.closed) { clearInterval(poll); setConnecting(false); onConnected() }
        } catch { /* COOP prevents access while popup is on Google's domain — ignore */ }
      }, 600)
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Could not get authorization URL.'
      setError(detail)
      setConnecting(false)
    }
  }

  const active = mailboxes.filter(m => m.is_active)
  const inactive = mailboxes.filter(m => !m.is_active)

  return (
    <div className="card" style={{ padding: '16px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: active.length > 0 || error ? 14 : 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Mail size={16} color="var(--primary-600)" />
          <span style={{ fontWeight: 600, fontSize: 14 }}>Gmail Connections</span>
          {active.length > 0 && (
            <span style={{ fontSize: 12, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Wifi size={12} /> {active.length} connected
            </span>
          )}
        </div>
        <button className="btn btn-primary" style={{ fontSize: 13, padding: '6px 16px' }} onClick={connectGmail} disabled={connecting}>
          <LogIn size={13} />
          {connecting ? 'Opening browser…' : mailboxes.length === 0 ? 'Connect Gmail Account' : 'Add Account'}
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: '#fff1f2', border: '1px solid #fecaca', borderRadius: 8, marginBottom: 12, fontSize: 13, color: '#991b1b' }}>
          <AlertCircle size={14} /> {error}
          <button style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#991b1b' }} onClick={() => setError('')}><X size={13} /></button>
        </div>
      )}

      {mailboxes.length === 0 && !error && (
        <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <WifiOff size={14} /> No Gmail accounts connected. Click "Connect Gmail Account" to start receiving RFQs automatically.
        </p>
      )}

      {active.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
          {active.map(mb => (
            <MailboxCard key={mb.id} mailbox={mb}
              syncing={syncing === mb.id || syncing === 'all'}
              onSync={() => onSync(mb.id)}
              onDisconnect={() => onDisconnect(mb.id)}
              onReauth={connectGmail} />
          ))}
        </div>
      )}

      {inactive.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Disconnected</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {inactive.map(mb => (
              <div key={mb.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                <WifiOff size={12} /> {mb.email_address}
                <button className="btn btn-secondary" style={{ fontSize: 11, padding: '3px 10px' }} onClick={connectGmail}>Re-authenticate</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Mailbox Card ─────────────────────────────────────────────────────────────

function MailboxCard({ mailbox: mb, syncing, onSync, onDisconnect, onReauth }: {
  mailbox: Mailbox; syncing: boolean; onSync: () => void; onDisconnect: () => void; onReauth?: () => void
}) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid var(--border)', background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Identity row — avatar + email/name get the full card width to themselves */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>
          {mb.email_address[0].toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={mb.display_name ? `${mb.display_name} <${mb.email_address}>` : mb.email_address}
          >
            {mb.email_address}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {mb.last_synced
              ? <span title={new Date(mb.last_synced).toLocaleString()}>Synced {formatRelativeDate(mb.last_synced)}</span>
              : 'Never synced — click Sync to fetch emails'}
          </div>
        </div>
      </div>

      {/* Actions row — own line so it never competes with the email/date for width */}
      <div style={{ display: 'flex', gap: 6 }}>
        <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: 11, flex: 1 }} onClick={onSync} disabled={syncing} title="Sync this mailbox">
          <RefreshCw size={12} className={syncing ? 'spin' : ''} /> {syncing ? 'Syncing…' : 'Sync'}
        </button>
        {onReauth && (
          <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: 11, flex: 1 }} onClick={onReauth} title="Re-authenticate (fix scope / expired token)">
            <LogIn size={12} /> Re-auth
          </button>
        )}
        <button style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', color: '#ef4444', display: 'flex', alignItems: 'center', flexShrink: 0 }} onClick={onDisconnect} title="Disconnect">
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  )
}

// ─── Email Panel (list + inline detail) ──────────────────────────────────────

function EmailPanel({ emails, allEmails, selected, loading, onSelect, onProcess, onNavigate, onSync, syncing }: {
  emails: RFQEmail[]
  allEmails: RFQEmail[]
  selected: RFQEmail | null
  loading: boolean
  onSelect: (e: RFQEmail | null) => void
  onProcess: (id: string) => Promise<void>
  onNavigate: (rfqId: string) => void
  onSync: () => void
  syncing: boolean
}) {
  const [processing, setProcessing] = useState<string | null>(null)
  const [detail, setDetail] = useState<any | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const selectEmail = async (email: RFQEmail) => {
    if (selected?.id === email.id) { onSelect(null); return }
    onSelect(email)
    setLoadingDetail(true)
    try { setDetail((await api.get(`/gmail/inbox/${email.id}`)).data) } catch { setDetail(null) }
    setLoadingDetail(false)
  }

  const handleProcess = async (id: string) => {
    setProcessing(id)
    await onProcess(id)
    setProcessing(null)
  }

  if (loading) {
    return (
      <div className="card" style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={32} style={{ marginBottom: 14, opacity: 0.3, animation: 'spin 1s linear infinite' }} />
        <p>Fetching emails from Gmail…</p>
      </div>
    )
  }

  if (allEmails.length === 0) {
    return (
      <div className="card" style={{ padding: 56, textAlign: 'center', color: 'var(--text-muted)' }}>
        <Mail size={48} style={{ marginBottom: 16, opacity: 0.2 }} />
        <p style={{ fontSize: 15, marginBottom: 8, fontWeight: 600 }}>No emails fetched yet</p>
        <p style={{ fontSize: 13, marginBottom: 20 }}>Connect a Gmail account above, then we'll sync automatically — or click below.</p>
        <button className="btn btn-primary" onClick={onSync} disabled={syncing}>
          <RefreshCw size={14} className={syncing ? 'spin' : ''} /> Fetch Emails Now
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: selected ? '400px 1fr' : '1fr', gap: 12, alignItems: 'start' }}>
      {/* ── Email list ── */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {/* list header */}
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {emails.length} email{emails.length !== 1 ? 's' : ''}
            {emails.length !== allEmails.length && ` (filtered from ${allEmails.length})`}
          </span>
          <div style={{ display: 'flex', gap: 6 }}>
            {selected && (
              <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 2 }} onClick={() => onSelect(null)} title="Close detail"><X size={14} /></button>
            )}
            <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 2 }} onClick={onSync} disabled={syncing} title="Refresh inbox">
              <RefreshCw size={14} className={syncing ? 'spin' : ''} />
            </button>
          </div>
        </div>

        {emails.length === 0 ? (
          <div style={{ padding: 28, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            No emails match the current filters.
          </div>
        ) : (
          <div style={{ overflowY: 'auto', maxHeight: 680 }}>
            {emails.map(e => {
              const isSel = selected?.id === e.id
              const unread = !e.is_processed
              return (
                <div
                  key={e.id}
                  onClick={() => selectEmail(e)}
                  style={{
                    padding: '11px 14px',
                    borderBottom: '1px solid var(--border)',
                    cursor: 'pointer',
                    background: isSel ? 'var(--primary-50)' : unread ? 'rgba(99,102,241,0.03)' : 'transparent',
                    borderLeft: isSel ? '3px solid var(--primary-600)' : unread ? '3px solid var(--primary-300)' : '3px solid transparent',
                    transition: 'background 0.1s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    {/* Avatar */}
                    <div style={{ width: 32, height: 32, borderRadius: '50%', background: emailTypeColor(e.email_type), display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 12, fontWeight: 700, flexShrink: 0, marginTop: 1 }}>
                      {(e.sender_name || e.sender_email || '?')[0].toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4 }}>
                        <span style={{ fontSize: 12, fontWeight: unread ? 700 : 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                          {e.sender_name || e.sender_email}
                        </span>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)', flexShrink: 0 }}>
                          {e.received_at ? formatRelativeDate(e.received_at) : ''}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: unread ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 2, color: unread ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                        {e.subject || '(no subject)'}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                        <span className={`badge ${emailTypeBadge[e.email_type] || 'badge-neutral'}`} style={{ fontSize: 9, padding: '1px 6px' }}>{e.email_type}</span>
                        {e.attachment_count > 0 && <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 2 }}><Paperclip size={9} />{e.attachment_count}</span>}
                        {e.rfq_id && <span style={{ fontSize: 10, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 2 }}><CheckCircle size={9} /> RFQ</span>}
                        {e.is_processed && !e.rfq_id && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>processed</span>}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Detail pane ── */}
      {selected && (
        <div className="card" style={{ padding: '20px 24px' }}>
          {loadingDetail ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
              <RefreshCw size={22} style={{ animation: 'spin 1s linear infinite', marginBottom: 10 }} /><br />Loading…
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, gap: 12 }}>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, flex: 1, lineHeight: 1.4 }}>{selected.subject || '(no subject)'}</h3>
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  {selected.rfq_id ? (
                    <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => onNavigate(selected.rfq_id!)}>
                      <ExternalLink size={13} /> View RFQ
                    </button>
                  ) : selected.email_type !== 'other' ? (
                    <button className="btn btn-primary" style={{ fontSize: 12 }} onClick={() => handleProcess(selected.id)} disabled={processing === selected.id}>
                      <MailOpen size={13} /> {processing === selected.id ? 'Creating RFQ…' : 'Create RFQ'}
                    </button>
                  ) : null}
                  <button style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 8px', cursor: 'pointer', display: 'flex' }} onClick={() => onSelect(null)}><X size={13} /></button>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16, padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: 12 }}>
                <div><span style={{ color: 'var(--text-muted)' }}>From: </span><b>{selected.sender_name || selected.sender_email}</b>{selected.sender_name && <span style={{ color: 'var(--text-muted)' }}> &lt;{selected.sender_email}&gt;</span>}</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Date: </span>{selected.received_at ? new Date(selected.received_at).toLocaleString() : '—'}</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Type: </span><span className={`badge ${emailTypeBadge[selected.email_type] || 'badge-neutral'}`} style={{ fontSize: 10 }}>{selected.email_type}</span></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Mailbox: </span>{selected.mailbox_email}</div>
                {selected.rfq_id && <div style={{ gridColumn: '1/-1', color: '#22c55e', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}><CheckCircle size={13} /> Linked to RFQ</div>}
              </div>

              {detail?.attachments?.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Attachments ({detail.attachments.length})</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {detail.attachments.map((att: any, i: number) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', background: '#f1f5f9', borderRadius: 6, fontSize: 12 }}>
                        <Paperclip size={11} color="#6b7280" />
                        <span>{att.filename}</span>
                        {att.file_size && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>({formatBytes(att.file_size)})</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Message</div>
                <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: '12px 14px', fontSize: 13, lineHeight: 1.75, maxHeight: 380, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', border: '1px solid var(--border)' }}>
                  {detail?.body_text || selected.body_text || '(No message body)'}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ─── RFQ Table ────────────────────────────────────────────────────────────────

function RFQTable({ rfqs, onSelect }: { rfqs: RFQRecord[]; onSelect: (id: string) => void }) {
  if (!rfqs.length) {
    return (
      <div className="card" style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
        <Inbox size={44} style={{ marginBottom: 14, opacity: 0.25 }} />
        <p>No RFQs found. Upload a document or connect Gmail to get started.</p>
      </div>
    )
  }
  return (
    <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
            {['RFQ #', 'Client', 'Project', 'Status', 'Priority', 'Source', 'Items', 'Created'].map(h => (
              <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rfqs.map(r => (
            <tr key={r.id} onClick={() => onSelect(r.id)} style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} className="table-row-hover">
              <td style={{ padding: '12px 16px', fontWeight: 600, fontSize: 13 }}>{r.rfq_number}</td>
              <td style={{ padding: '12px 16px', fontSize: 13 }}>{r.client_name || '—'}</td>
              <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.project_name || '—'}</td>
              <td style={{ padding: '12px 16px' }}><span className={`badge ${statusBadge[r.status] || 'badge-neutral'}`} style={{ fontSize: 11 }}>{r.status}</span></td>
              <td style={{ padding: '12px 16px' }}>
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: priorityColor[r.priority] || '#6b7280', marginRight: 6 }} />
                <span style={{ fontSize: 12 }}>{r.priority}</span>
              </td>
              <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-muted)' }}>{r.source}</td>
              <td style={{ padding: '12px 16px', fontSize: 13 }}>{r.line_item_count}</td>
              <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-muted)' }}>{new Date(r.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
