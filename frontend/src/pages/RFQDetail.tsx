import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, FileText, Upload, CheckCircle, RefreshCw,
  BarChart2, Download, Paperclip,
  DollarSign, TrendingUp
} from 'lucide-react'
import { api } from '../api/client'
import AttachmentCard from '../components/rfq/AttachmentCard'

interface RFQ {
  id: string
  rfq_number: string
  client_name: string | null
  client_email: string | null
  project_name: string | null
  project_reference: string | null
  scope_summary: string | null
  status: string
  priority: string
  revision_number: number
  source: string
  subject: string | null
  notes: string | null
  enquiry_date: string | null
  deadline: string | null
  created_at: string
  attachment_count: number
  line_item_count: number
}

interface Attachment {
  id: string
  original_filename: string
  file_category: string
  document_type: string
  classification_confidence: number | null
  extraction_status: string
  revision_number: string | null
  document_number: string | null
  file_size: number | null
  storage_url: string | null
  created_at: string
}

const statusBadge: Record<string, string> = {
  received: 'badge-neutral', classifying: 'badge-warning', extracting: 'badge-warning',
  review: 'badge-primary', validated: 'badge-success', costing: 'badge-primary',
  costing_ready: 'badge-success', quoted: 'badge-success', closed: 'badge-neutral', rejected: 'badge-error',
}

const TABS = [
  { id: 'overview',    label: 'Overview',    icon: FileText },
  { id: 'attachments', label: 'Attachments', icon: Paperclip },
  { id: 'costing',     label: 'Costing',     icon: DollarSign },
]

export default function RFQDetail() {
  const { rfqId } = useParams<{ rfqId: string }>()
  const navigate = useNavigate()
  const [rfq, setRfq] = useState<RFQ | null>(null)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [autoCosting, setAutoCosting] = useState<any>(null)
  const [costingLoading, setCostingLoading] = useState(false)

  const loadRFQ = useCallback(async () => {
    if (!rfqId) return
    try {
      const [rfqRes, attRes] = await Promise.all([
        api.get(`/rfq/${rfqId}`),
        api.get(`/rfq/${rfqId}/attachments`),
      ])
      setRfq(rfqRes.data)
      setAttachments(attRes.data)
    } catch {/* handled */}
    setLoading(false)
  }, [rfqId])

  const loadAutoCosting = useCallback(async () => {
    if (!rfqId) return
    try {
      const res = await api.get(`/rfq/${rfqId}/auto-costing`)
      setAutoCosting(res.data)
    } catch {
      setAutoCosting(null)
    }
  }, [rfqId])

  useEffect(() => { loadAutoCosting() }, [loadAutoCosting])

  useEffect(() => { loadRFQ() }, [loadRFQ])

  const handleAutoCost = async () => {
    if (!rfqId) return
    setCostingLoading(true)
    try {
      await api.post(`/rfq/${rfqId}/auto-costing`)
      setActiveTab('costing')
      // Poll until costing_ready or failed
      let attempts = 0
      const poll = async () => {
        attempts++
        try {
          const res = await api.get(`/rfq/${rfqId}/auto-costing`)
          setAutoCosting(res.data)
          await loadRFQ()
          setCostingLoading(false)
        } catch {
          if (attempts < 20) setTimeout(poll, 3000)
          else setCostingLoading(false)
        }
      }
      setTimeout(poll, 3000)
    } catch {
      setCostingLoading(false)
    }
  }

  const handleDownloadExcel = async () => {
    if (!rfqId) return
    try {
      const res = await api.post(`/rfq/${rfqId}/auto-costing/download-excel`, {}, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `${rfqId}_costing_sheet.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch {/* handled */}
  }

  const handleApprove = async () => {
    if (!rfqId) return
    try {
      await api.post(`/rfq/${rfqId}/approve`)
      await loadRFQ()
    } catch {/* handled */}
  }

  const handleConvertToJob = async () => {
    if (!rfqId) return
    try {
      const res = await api.post(`/rfq/${rfqId}/convert-to-job`)
      navigate(`/quote-summary/${res.data.job_id}`)
    } catch {/* handled */}
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || !rfqId) return
    setUploading(true)
    for (const file of Array.from(files)) {
      const form = new FormData()
      form.append('file', file)
      try {
        await api.post(`/rfq/${rfqId}/attachments`, form, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      } catch {/* handled */}
    }
    setUploading(false)
    loadRFQ()
  }

  if (loading) return <div className="animate-fade-in" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading RFQ…</div>
  if (!rfq) return <div className="animate-fade-in" style={{ padding: 40, textAlign: 'center' }}>RFQ not found.</div>

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="page-title-bar">
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <button className="btn btn-secondary" style={{ padding: '6px 10px', marginTop: 2 }} onClick={() => navigate('/rfq')}>
            <ArrowLeft size={15} />
          </button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <h1 className="page-title" style={{ margin: 0 }}>{rfq.rfq_number}</h1>
              <span className={`badge ${statusBadge[rfq.status] || 'badge-neutral'}`}>{rfq.status}</span>
              {rfq.revision_number > 0 && (
                <span className="badge badge-neutral">Rev {rfq.revision_number}</span>
              )}
            </div>
            <p className="page-subtitle" style={{ margin: 0 }}>
              {rfq.client_name || 'Unknown Client'} — {rfq.project_name || rfq.subject || 'No project name'}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <label className="btn btn-secondary" style={{ cursor: 'pointer' }}>
            <Upload size={14} /> {uploading ? 'Uploading…' : 'Upload File'}
            <input type="file" multiple style={{ display: 'none' }} onChange={handleFileUpload} disabled={uploading} />
          </label>
          <button
            className="btn btn-primary"
            onClick={handleAutoCost}
            disabled={costingLoading}
            title="Extract PDF attachments and auto-generate costing sheet"
          >
            <TrendingUp size={14} /> {costingLoading ? 'Running Costing…' : 'Auto-Cost'}
          </button>
          {autoCosting && (
            <button className="btn btn-secondary" onClick={handleDownloadExcel}>
              <Download size={14} /> Download Excel
            </button>
          )}
          {rfq.status === 'costing_ready' && (
            <button className="btn btn-primary" onClick={handleConvertToJob}>
              <BarChart2 size={14} /> Convert to Job
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20, borderBottom: '1px solid var(--border)' }}>
        {TABS.map(t => {
          const Icon = t.icon
          const isActive = activeTab === t.id
          const badge = t.id === 'attachments' ? attachments.length || null : null
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              style={{
                padding: '9px 18px',
                background: 'none',
                border: 'none',
                borderBottom: isActive ? '2px solid var(--primary-600)' : '2px solid transparent',
                color: isActive ? 'var(--primary-600)' : 'var(--text-muted)',
                fontWeight: isActive ? 600 : 400,
                cursor: 'pointer',
                fontSize: 13,
                marginBottom: -1,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Icon size={14} /> {t.label}
              {badge != null && (
                <span style={{
                  background: 'var(--primary-600)',
                  color: '#fff',
                  borderRadius: 10,
                  fontSize: 10,
                  padding: '1px 6px',
                  fontWeight: 700,
                  lineHeight: 1.6,
                }}>
                  {badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && <OverviewTab rfq={rfq} onUpdate={loadRFQ} />}
      {activeTab === 'attachments' && (
        <div className="grid grid-cols-3 gap-4">
          {attachments.length === 0
            ? <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1/-1' }}>No attachments uploaded yet.</div>
            : attachments.map(att => (
              <AttachmentCard key={att.id} attachment={att} rfqId={rfq.id} onUpdate={loadRFQ} />
            ))
          }
        </div>
      )}
      {activeTab === 'costing' && (
        <CostingTab
          rfq={rfq}
          costing={autoCosting}
          loading={costingLoading}
          onRunCosting={handleAutoCost}
          onDownloadExcel={handleDownloadExcel}
        />
      )}

    </div>
  )
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────
function OverviewTab({ rfq, onUpdate }: { rfq: RFQ; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    client_name: rfq.client_name || '',
    client_email: rfq.client_email || '',
    project_name: rfq.project_name || '',
    project_reference: rfq.project_reference || '',
    scope_summary: rfq.scope_summary || '',
    notes: rfq.notes || '',
    priority: rfq.priority || 'normal',
  })
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await api.put(`/rfq/${rfq.id}`, form)
      setEditing(false)
      onUpdate()
    } catch {/* handled */}
    setSaving(false)
  }

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Details card */}
      <div className="card" style={{ gridColumn: '1/3', padding: '20px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>RFQ Details</h3>
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: '4px 12px' }} onClick={() => setEditing(!editing)}>
            {editing ? 'Cancel' : 'Edit'}
          </button>
        </div>

        {editing ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {[
              { key: 'client_name', label: 'Client Name' },
              { key: 'client_email', label: 'Client Email' },
              { key: 'project_name', label: 'Project Name' },
              { key: 'project_reference', label: 'Project Reference' },
            ].map(f => (
              <div key={f.key}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>{f.label}</label>
                <input
                  className="form-input"
                  value={(form as any)[f.key]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                />
              </div>
            ))}
            <div style={{ gridColumn: '1/-1' }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Scope Summary</label>
              <textarea
                className="form-input"
                rows={3}
                value={form.scope_summary}
                onChange={e => setForm(p => ({ ...p, scope_summary: e.target.value }))}
              />
            </div>
            <div style={{ gridColumn: '1/-1', display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {[
              { label: 'Client Name', value: rfq.client_name },
              { label: 'Client Email', value: rfq.client_email },
              { label: 'Project Name', value: rfq.project_name },
              { label: 'Project Reference', value: rfq.project_reference },
              { label: 'Enquiry Date', value: rfq.enquiry_date ? new Date(rfq.enquiry_date).toLocaleDateString() : null },
              { label: 'Deadline', value: rfq.deadline ? new Date(rfq.deadline).toLocaleDateString() : null },
              { label: 'Source', value: rfq.source },
              { label: 'Priority', value: rfq.priority },
            ].map(f => (
              <div key={f.label}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 3 }}>{f.label}</div>
                <div style={{ fontSize: 14 }}>{f.value || '—'}</div>
              </div>
            ))}
            {rfq.scope_summary && (
              <div style={{ gridColumn: '1/-1' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 3 }}>Scope Summary</div>
                <div style={{ fontSize: 14, lineHeight: 1.6 }}>{rfq.scope_summary}</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pipeline card */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600 }}>Pipeline Stage</h3>
        {[
          { label: 'Received',   done: true },
          { label: 'Classified', done: !['received'].includes(rfq.status) },
          { label: 'Extracted',  done: !['received','classifying','extracting'].includes(rfq.status) },
          { label: 'Reviewed',   done: ['validated','costing','costing_ready','quoted','closed'].includes(rfq.status) },
          { label: 'Costing',    done: ['costing_ready','quoted','closed'].includes(rfq.status) },
          { label: 'Quoted',     done: ['quoted','closed'].includes(rfq.status) },
        ].map((step, i) => (
          <div key={step.label} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <div style={{
              width: 22, height: 22, borderRadius: '50%',
              background: step.done ? '#22c55e' : 'var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              {step.done && <CheckCircle size={14} color="#fff" />}
            </div>
            <span style={{ fontSize: 13, color: step.done ? 'var(--text-primary)' : 'var(--text-muted)' }}>{step.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Costing Tab ─────────────────────────────────────────────────────────────
function CostingTab({
  rfq, costing, loading, onRunCosting, onDownloadExcel,
}: {
  rfq: RFQ
  costing: any
  loading: boolean
  onRunCosting: () => void
  onDownloadExcel: () => void
}) {
  const c = costing?.costing
  const extraction = costing?.extraction

  const fmt = (n: number | undefined) =>
    n !== undefined ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'

  if (loading) {
    return (
      <div className="card" style={{ padding: 48, textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>⚙️</div>
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>
          Running drawing costing pipeline on PDF attachments…
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>This may take 20–60 seconds.</p>
      </div>
    )
  }

  if (!costing) {
    return (
      <div className="card" style={{ padding: 48, textAlign: 'center' }}>
        <TrendingUp size={40} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
        <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>No Costing Sheet Yet</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>
          Click <strong>Auto-Cost</strong> to automatically extract members from PDF attachments
          and generate the Job Costing Sheet based on this email's details.
        </p>
        <button className="btn btn-primary" onClick={onRunCosting}>
          <TrendingUp size={14} /> Run Auto-Costing
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Customer / source info */}
      <div className="card" style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>Client</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{rfq.client_name || '—'}</div>
          {rfq.project_name && <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{rfq.project_name}</div>}
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Computed {costing.computed_at ? new Date(costing.computed_at).toLocaleString() : ''}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Source: {(costing.source_files || []).join(', ') || '—'}</div>
          {costing.failed_files?.length > 0 && (
            <div style={{ fontSize: 12, color: '#f59e0b' }}>⚠ {costing.failed_files.length} file(s) failed</div>
          )}
        </div>
        <button className="btn btn-primary" onClick={onDownloadExcel} style={{ marginLeft: 16 }}>
          <Download size={14} /> Download Excel
        </button>
      </div>

      {/* Selling price highlight */}
      {c && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {[
            { label: 'Total Steel', value: `${fmt(c.total_steel_kg)} kg`, color: 'var(--primary-600)' },
            { label: 'Grand Total', value: `AED ${fmt(c.grand_total)}`, color: '#64748b' },
            { label: 'Selling Price', value: `AED ${fmt(c.selling_price)}`, color: '#16a34a' },
            { label: `Net Profit (${c.profit_pct}%)`, value: `AED ${fmt(c.net_profit)}`, color: c.net_profit > 0 ? '#16a34a' : '#ef4444' },
          ].map(kpi => (
            <div key={kpi.label} className="card" style={{ padding: '16px 20px' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>{kpi.label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: kpi.color }}>{kpi.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Cost breakdown table */}
      {c && (
        <div className="card" style={{ padding: '20px 24px' }}>
          <h3 style={{ margin: '0 0 14px', fontSize: 15, fontWeight: 600 }}>Cost Breakdown</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>Item</th>
                <th style={{ textAlign: 'right', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>Qty</th>
                <th style={{ textAlign: 'right', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>Cost (AED)</th>
              </tr>
            </thead>
            <tbody>
              {[
                { item: 'Steel Material',       qty: `${fmt(c.total_steel_kg)} kg`,  cost: c.steel_mat_cost },
                { item: 'Bolts',                qty: `${c.bolts} nos`,               cost: c.bolt_cost },
                { item: 'Paint Material',       qty: `${c.paint_litres} L`,          cost: c.paint_mat_cost },
                { item: 'Structural Welding',   qty: `${c.welding_mh} MH`,           cost: c.weld_cost },
                { item: 'Fabrication',          qty: `${c.fabrication_mh} MH`,       cost: c.fab_cost },
                { item: 'Blasting',             qty: `${c.surface_area_sqm} m²`,     cost: c.blast_cost },
                { item: 'Painting',             qty: `${c.surface_area_sqm} m²`,     cost: c.paint_app_cost },
                { item: 'MPI / DPT',            qty: `${c.mpi_visits} visits`,       cost: c.mpi_cost },
                { item: 'QA/QC',                qty: '1',                            cost: c.qaqc_cost },
                { item: 'Packing',              qty: '1',                            cost: c.packing_cost },
                { item: 'Overhead',             qty: '—',                            cost: c.overhead },
                { item: 'Consumables',          qty: '—',                            cost: c.consumables },
              ].map(row => (
                <tr key={row.item} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '7px 8px' }}>{row.item}</td>
                  <td style={{ padding: '7px 8px', textAlign: 'right', color: 'var(--text-muted)' }}>{row.qty}</td>
                  <td style={{ padding: '7px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.cost)}</td>
                </tr>
              ))}
              <tr style={{ fontWeight: 700, borderTop: '2px solid var(--border)' }}>
                <td style={{ padding: '8px 8px' }} colSpan={2}>Selling Price (incl. {c.markup_pct}% markup)</td>
                <td style={{ padding: '8px 8px', textAlign: 'right', color: '#16a34a', fontVariantNumeric: 'tabular-nums' }}>AED {fmt(c.selling_price)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Extracted members */}
      {extraction?.members?.length > 0 && (
        <div className="card" style={{ padding: '20px 24px' }}>
          <h3 style={{ margin: '0 0 14px', fontSize: 15, fontWeight: 600 }}>Structural Members Extracted</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Section', 'Role', 'Length (m)', 'kg/m', 'Weight (kg)'].map(h => (
                  <th key={h} style={{ textAlign: h === 'Section' || h === 'Role' ? 'left' : 'right', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {extraction.members.map((m: any, i: number) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '7px 8px', fontFamily: 'monospace' }}>{m.section}</td>
                  <td style={{ padding: '7px 8px', color: 'var(--text-muted)' }}>{m.role || '—'}</td>
                  <td style={{ padding: '7px 8px', textAlign: 'right' }}>{m.total_length_m}</td>
                  <td style={{ padding: '7px 8px', textAlign: 'right' }}>{m.kg_per_m ?? '—'}</td>
                  <td style={{ padding: '7px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{m.weight_kg ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Re-run button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-secondary" onClick={onRunCosting} disabled={loading}>
          <RefreshCw size={13} /> Re-run Costing
        </button>
      </div>
    </div>
  )
}
