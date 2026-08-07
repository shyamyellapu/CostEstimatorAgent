import { useCallback, useEffect, useState, type Dispatch, type SetStateAction, type ChangeEvent } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  AlertTriangle, CheckCircle, Clock, FileText,
  RefreshCw, Upload, XCircle, Download,
  FileSpreadsheet, Info,
} from 'lucide-react'

// ─── Types ──────────────────────────────────────────────────────
interface BomItem {
  id: string
  description: string
  category: string
  section_type: string | null
  section_size: string | null
  material_grade: string | null
  qty: number | null
  length_mm: number | null
  width_mm: number | null
  thickness_mm: number | null
  unit_weight_kg: number | null
  total_weight_kg: number | null
  confidence: number | null
  review_required: boolean
}

interface Costing {
  total_steel_kg: number
  surface_area_sqm: number
  bolts: number
  paint_litres: number
  mpi_visits: number
  welding_mh: number
  fabrication_mh: number
  steel_mat_cost: number
  bolt_cost: number
  paint_mat_cost: number
  weld_cost: number
  fab_cost: number
  blast_cost: number
  paint_app_cost: number
  mpi_cost: number
  qaqc_cost: number
  packing_cost: number
  subtotal: number
  overhead: number
  consumables: number
  grand_total: number
  selling_price: number
  net_profit: number
  profit_pct: number
  markup_pct: number
}

interface Flag {
  field: string
  message: string
  severity?: string
}

interface WorkflowResult {
  job_id: string
  job_number: string
  project_information: {
    project_name?: string
    client_name?: string
    drawing_number?: string
  }
  bom_items: BomItem[]
  total_steel_kg: number
  costing: Costing
  customer_info?: Record<string, string> | null
  overall_confidence: number
  summary: string
  flags: Flag[]
  status: string
  can_generate_excel: boolean
  markup_pct: number
}

// ─── Helpers ─────────────────────────────────────────────────────
function fmt(n: number | null | undefined, decimals = 2) {
  if (n == null) return '—'
  return n.toLocaleString('en-AE', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })
}

function aed(n: number | null | undefined) {
  if (n == null) return '—'
  return `AED ${n.toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function ConfidencePill({ value }: { value: number | null }) {
  if (value == null) return <span style={{ color: 'var(--text-muted)' }}>—</span>
  const pct = Math.round(value * 100)
  const color = pct >= 85 ? 'var(--success-600)' : pct >= 65 ? 'var(--warning-600)' : 'var(--error-600)'
  return (
    <span style={{ fontSize: '0.8rem', fontWeight: 700, color }}>
      {pct}%
    </span>
  )
}

type Step = { label: string; done: boolean; active: boolean }

function ProcessingProgress({ steps }: { steps: Step[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
      {steps.map((s, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.875rem' }}>
          {s.done
            ? <CheckCircle size={18} style={{ color: 'var(--success-600)', flexShrink: 0 }} />
            : s.active
            ? <RefreshCw size={18} style={{ color: 'var(--primary-600)', flexShrink: 0, animation: 'spin 1s linear infinite' }} />
            : <Clock size={18} style={{ color: 'var(--gray-300)', flexShrink: 0 }} />}
          <span style={{
            color: s.done ? 'var(--success-700)' : s.active ? 'var(--primary-700)' : 'var(--text-muted)',
            fontWeight: s.active ? 600 : 400,
          }}>
            {s.label}
          </span>
        </div>
      ))}
    </div>
  )
}

type Tab = 'bom' | 'costing' | 'summary'

type ManualForm = {
  structural_steel_kg: string
  handrail_kg: string
  grating_kg: string
  bolts_qty: string
  paint_litres: string
  project_name: string
  client_name: string
  drawing_number: string
}

function ManualEntryPanel({
  manualForm, setManualForm, markupPct, setMarkupPct, onSubmit, onBack, loading,
}: {
  manualForm: ManualForm
  setManualForm: Dispatch<SetStateAction<ManualForm>>
  markupPct: number
  setMarkupPct: (n: number) => void
  onSubmit: () => void
  onBack: () => void
  loading: boolean
}) {
  const update = (field: keyof ManualForm) => (e: ChangeEvent<HTMLInputElement>) =>
    setManualForm(prev => ({ ...prev, [field]: e.target.value }))

  const canSubmit = parseFloat(manualForm.structural_steel_kg) > 0 && !loading

  return (
    <div className="card" style={{ marginTop: '1.5rem' }}>
      <div className="card-header"><h3 className="card-title">Manual BOQ Entry</h3></div>
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

        <div className="form-group">
          <label className="form-label">Structural Steel Total Weight (kg) *</label>
          <input
            type="number" min={0} className="form-input"
            value={manualForm.structural_steel_kg}
            onChange={update('structural_steel_kg')}
          />
        </div>

        <div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Optional — leave blank to use ratio-based estimates
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div className="form-group">
              <label className="form-label">Handrails (kg)</label>
              <input type="number" min={0} className="form-input" value={manualForm.handrail_kg} onChange={update('handrail_kg')} />
            </div>
            <div className="form-group">
              <label className="form-label">Grating (kg)</label>
              <input type="number" min={0} className="form-input" value={manualForm.grating_kg} onChange={update('grating_kg')} />
            </div>
            <div className="form-group">
              <label className="form-label">M20×90 Bolts (qty)</label>
              <input type="number" min={0} className="form-input" value={manualForm.bolts_qty} onChange={update('bolts_qty')} />
            </div>
            <div className="form-group">
              <label className="form-label">Paint Material (litres)</label>
              <input type="number" min={0} className="form-input" value={manualForm.paint_litres} onChange={update('paint_litres')} />
            </div>
          </div>
        </div>

        <div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Project Information (optional)
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
            <div className="form-group">
              <label className="form-label">Project Name</label>
              <input className="form-input" value={manualForm.project_name} onChange={update('project_name')} />
            </div>
            <div className="form-group">
              <label className="form-label">Client Name</label>
              <input className="form-input" value={manualForm.client_name} onChange={update('client_name')} />
            </div>
            <div className="form-group">
              <label className="form-label">Drawing Number</label>
              <input className="form-input" value={manualForm.drawing_number} onChange={update('drawing_number')} />
            </div>
          </div>
        </div>

        <div className="form-group" style={{ maxWidth: 300 }}>
          <label className="form-label">Markup %: {markupPct}%</label>
          <input
            type="range" min={0} max={80} value={markupPct}
            onChange={e => setMarkupPct(Number(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem' }}>
          <button className="btn btn-ghost" onClick={onBack} disabled={loading}>
            ← Back to Upload
          </button>
          <button className="btn btn-primary" onClick={onSubmit} disabled={!canSubmit}>
            {loading ? 'Generating…' : 'Generate Costing Sheet →'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DrawingCosting() {
  const { jobId } = useParams<{ jobId?: string }>()
  const navigate = useNavigate()
  const [files, setFiles] = useState<File[]>([])
  const [markupPct, setMarkupPct] = useState(34)
  const [loading, setLoading] = useState(false)
  const [loadingReview, setLoadingReview] = useState(!!jobId)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<WorkflowResult | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('bom')
  const [processingStep, setProcessingStep] = useState(0)
  const [customer, setCustomer] = useState({
    customerName: '', refNo: '', enquiryNo: '', jobNo: '', attention: '', contact: '',
  })
  const [showCustomerModal, setShowCustomerModal] = useState(false)
  const [showManualEntry, setShowManualEntry] = useState(false)
  const [manualForm, setManualForm] = useState({
    structural_steel_kg: '',
    handrail_kg: '',
    grating_kg: '',
    bolts_qty: '',
    paint_litres: '',
    project_name: '',
    client_name: '',
    drawing_number: '',
  })

  // Reopening a previously-created job from Job History — load its saved review
  // state (BOM items + costing) instead of showing the upload screen.
  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    setLoadingReview(true)
    setError(null)
    console.log(`%c[DrawingCosting] Reopening job ${jobId}`, 'color:#6366f1')
    api.get(`/drawing-costing/${jobId}/review?markup_pct=${markupPct}`)
      .then(res => {
        if (cancelled) return
        const data: WorkflowResult = res.data
        setResult(data)
        setMarkupPct(data.markup_pct ?? 34)
        setCustomer(prev => ({ ...prev, jobNo: data.job_number, ...(data.customer_info || {}) }))
        setActiveTab('bom')
        console.log('[DrawingCosting] Reopened job:', data)
      })
      .catch(e => {
        if (cancelled) return
        console.error('[DrawingCosting] Failed to load job for review:', e?.response?.data?.detail || e?.message)
        setError(e?.response?.data?.detail || 'Could not load this job.')
      })
      .finally(() => {
        if (!cancelled) setLoadingReview(false)
      })
    return () => { cancelled = true }
    // Only re-run when the route's jobId changes — markupPct is intentionally
    // captured once at load time, not on every slider tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  // New 4-step pipeline matching LlamaParse → LLM flow
  const processingSteps: Step[] = [
    { label: 'Uploading files',              done: processingStep > 0, active: processingStep === 0 && loading },
    { label: 'Parsing documents (LlamaParse)', done: processingStep > 1, active: processingStep === 1 },
    { label: 'Extracting data (LLM)',          done: processingStep > 2, active: processingStep === 2 },
    { label: 'Computing costs (Python)',        done: processingStep > 3, active: processingStep === 3 },
  ]

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    multiple: true,
    onDrop: (accepted) => setFiles(prev => [...prev, ...accepted]),
  })

  const removeFile = (i: number) => setFiles(files.filter((_, idx) => idx !== i))

  const handleAnalyse = async () => {
    if (!files.length) return
    setLoading(true)
    setError(null)
    setProcessingStep(0)
    setResult(null)

    console.group(`%c[DrawingCosting] Analysis started — ${files.length} file(s)`, 'color:#6366f1;font-weight:bold')
    console.log('Files:', files.map(f => ({ name: f.name, size: `${(f.size / 1024 / 1024).toFixed(2)} MB`, type: f.type })))
    console.log('Markup %:', markupPct)
    console.time('[DrawingCosting] Total time')

    let t0: ReturnType<typeof setTimeout> | undefined

    try {
      const fd = new FormData()
      files.forEach(f => fd.append('files', f))
      fd.append('markup_pct', String(markupPct))

      // Steps 0 (upload) and 1 (LlamaParse) advance on a timer because
      // we can't know when LlamaParse finishes from the frontend.
      // Steps 2 (LLM) and 3 (Computing costs) are flashed briefly AFTER
      // the API returns — they are near-instant on the backend.
      t0 = setTimeout(() => {
        setProcessingStep(1)
        console.log('%c[DrawingCosting] Step 2/4: Parsing with LlamaParse…', 'color:#6366f1')
      }, 2000)

      console.log('%c[DrawingCosting] → POST /api/drawing-costing/analyse', 'color:#0ea5e9')
      const res = await api.post('/drawing-costing/analyse', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600_000,
      })

      clearTimeout(t0)

      // LlamaParse + LLM finished — briefly show remaining steps before revealing result
      setProcessingStep(2)
      console.log('%c[DrawingCosting] Step 3/4: LLM extraction complete', 'color:#6366f1')
      await new Promise(r => setTimeout(r, 400))

      setProcessingStep(3)
      console.log('%c[DrawingCosting] Step 4/4: Computing costs…', 'color:#6366f1')
      await new Promise(r => setTimeout(r, 400))

      setProcessingStep(4)

      const data: WorkflowResult = res.data
      console.log('%c[DrawingCosting] ✓ Response received', 'color:#22c55e;font-weight:bold')
      console.log('Job ID:', data.job_id, '|', 'Job #:', data.job_number)
      console.log('Status:', data.status, '| Confidence:', data.overall_confidence)
      console.log('Total steel kg:', data.total_steel_kg)
      console.log('Summary:', data.summary)

      if (data.bom_items?.length) {
        console.group(`%c[DrawingCosting] BOM items (${data.bom_items.length})`, 'color:#f59e0b')
        console.table(
          data.bom_items.map(b => ({
            description: b.description,
            category: b.category,
            section: b.section_size ?? '—',
            qty: b.qty ?? '—',
            'weight kg': b.total_weight_kg ?? '—',
            confidence: b.confidence != null ? `${Math.round(b.confidence * 100)}%` : '—',
            review: b.review_required ? '⚠ YES' : 'OK',
          }))
        )
        console.groupEnd()
      } else {
        console.warn('[DrawingCosting] No BOM items extracted')
      }

      if (data.flags?.length) {
        console.group('%c[DrawingCosting] Flags / ambiguities', 'color:#ef4444')
        data.flags.forEach(f => console.warn(`  [${f.severity ?? 'FLAG'}] ${f.field}: ${f.message}`))
        console.groupEnd()
      }

      console.group('%c[DrawingCosting] Costing breakdown', 'color:#10b981')
      console.table({
        'Total steel (kg)':  data.costing.total_steel_kg,
        'Selling price':     `AED ${data.costing.selling_price}`,
        'Grand total':       `AED ${data.costing.grand_total}`,
        'Net profit':        `AED ${data.costing.net_profit}`,
        'Profit %':          `${data.costing.profit_pct}%`,
        'Markup %':          `${data.costing.markup_pct}%`,
      })
      console.groupEnd()

      console.log('%c[DrawingCosting] Full response object:', 'color:#64748b', data)
      console.timeEnd('[DrawingCosting] Total time')
      console.groupEnd()

      setResult(data)
      setActiveTab('bom')

    } catch (e: any) {
      clearTimeout(t0)
      const msg = 'The AI pipeline could not extract data from this document. You can enter the quantities manually to generate the costing sheet.'
      console.error('%c[DrawingCosting] ✗ Error:', 'color:#ef4444;font-weight:bold', e?.response?.data?.detail || e?.message)
      console.error('Full error:', e)
      console.timeEnd('[DrawingCosting] Total time')
      console.groupEnd()
      setError(msg)
      setShowManualEntry(true)
    } finally {
      setLoading(false)
    }
  }

  const handleManualEntry = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = {
        structural_steel_kg: parseFloat(manualForm.structural_steel_kg),
        handrail_kg:  manualForm.handrail_kg  ? parseFloat(manualForm.handrail_kg)  : null,
        grating_kg:   manualForm.grating_kg   ? parseFloat(manualForm.grating_kg)   : null,
        bolts_qty:    manualForm.bolts_qty    ? parseFloat(manualForm.bolts_qty)    : null,
        paint_litres: manualForm.paint_litres ? parseFloat(manualForm.paint_litres) : null,
        markup_pct:   markupPct,
        project_name:   manualForm.project_name   || null,
        client_name:    manualForm.client_name    || null,
        drawing_number: manualForm.drawing_number || null,
      }
      const res = await api.post('/drawing-costing/manual-entry', payload)
      setResult(res.data)
      setActiveTab('bom')
      setShowManualEntry(false)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to create manual costing entry.')
    } finally {
      setLoading(false)
    }
  }

  const handleRecalculate = async () => {
    if (!result) return
    setLoading(true)
    setError(null)
    console.log(`%c[DrawingCosting] Recalculating job ${result.job_id} at ${markupPct}% markup`, 'color:#6366f1')
    try {
      const res = await api.post(
        `/drawing-costing/${result.job_id}/recalculate?markup_pct=${markupPct}`
      )
      console.log('[DrawingCosting] Recalculate result:', res.data)
      setResult(prev => prev
        ? { ...prev, total_steel_kg: res.data.total_steel_kg, costing: res.data.costing }
        : null
      )
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message
      console.error('[DrawingCosting] Recalculate failed:', msg)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  // "Generate Excel" always opens the customer-info modal first — customer details are required
  // by the backend (and persisted to the job) before a costing sheet can be produced.
  const handleGenerateExcel = () => {
    if (!result) return
    setError(null)
    setShowCustomerModal(true)
  }

  const doGenerateExcel = async () => {
    if (!result) return
    setExporting(true)
    setError(null)
    console.log(`%c[DrawingCosting] Generating Excel for job ${result.job_id}`, 'color:#6366f1')
    try {
      const res = await api.post(
        `/drawing-costing/${result.job_id}/generate-excel`,
        { customer, markup_pct: markupPct },
        { responseType: 'blob' }
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `JobCosting_${customer.jobNo || result.job_number}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      setShowCustomerModal(false)
      console.log('[DrawingCosting] Excel downloaded ✓')
    } catch (e: any) {
      // With responseType: 'blob', an error response body arrives as a Blob, not JSON.
      let msg = e?.message
      if (e?.response?.data instanceof Blob) {
        try {
          msg = JSON.parse(await e.response.data.text())?.detail || msg
        } catch { /* not JSON — keep the generic message */ }
      } else {
        msg = e?.response?.data?.detail || msg
      }
      console.error('[DrawingCosting] Excel generation failed:', msg)
      setError(msg)
    } finally {
      setExporting(false)
    }
  }

  const handleBomEdit = async (id: string, field: string, value: any) => {
    if (!result) return
    console.log(`[DrawingCosting] Editing BOM item ${id}: ${field} = ${value}`)
    try {
      const res = await api.patch(`/drawing-costing/${result.job_id}/bom-items/${id}`, { [field]: value })
      setResult(prev => prev
        ? { ...prev, bom_items: prev.bom_items.map(i => i.id === id ? { ...i, ...res.data } : i) }
        : null
      )
    } catch (e: any) {
      console.error('[DrawingCosting] BOM edit failed:', e?.response?.data?.detail || e?.message)
      setError(e?.message)
    }
  }

  const getFileExt = (name: string) => name.split('.').pop()?.toLowerCase() || 'other'
  const fileIconClass = (ext: string) =>
    ext === 'pdf' ? 'pdf'
    : ['png', 'jpg', 'jpeg'].includes(ext) ? 'img'
    : ['xlsx', 'xls'].includes(ext) ? 'xlsx'
    : ['docx', 'doc'].includes(ext) ? 'docx'
    : 'other'

  // ── LOADING (reopening an existing job) ──────────────────────────
  if (jobId && loadingReview) {
    return (
      <div className="page-body" style={{ maxWidth: 700, margin: '0 auto', padding: '3rem 1.5rem', textAlign: 'center' }}>
        <div className="spinner spinner-lg" style={{ margin: '0 auto' }} />
        <p style={{ marginTop: '1rem', color: 'var(--text-muted)' }}>Loading job…</p>
      </div>
    )
  }

  // ── FAILED TO REOPEN AN EXISTING JOB ─────────────────────────────
  if (jobId && !result) {
    return (
      <div className="page-body" style={{ maxWidth: 700, margin: '0 auto', padding: '1.5rem' }}>
        <div className="alert alert-error">{error || 'Could not load this job.'}</div>
        <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={() => navigate('/history')}>
          ← Back to Job History
        </button>
      </div>
    )
  }

  // ── UPLOAD SCREEN ──────────────────────────────────────────────
  if (!result) {
    return (
      <div className="page-body" style={{ maxWidth: 700, margin: '0 auto', padding: '1.5rem' }}>
        <div className="page-title-bar">
          <h1 className="page-title">Drawing Costing</h1>
          <p className="page-subtitle">
            LlamaParse parses your documents → LLM extracts steel data → Python calculates costs → you review & export
          </p>
        </div>

        {showManualEntry ? (
          <>
            {error && <div className="alert alert-error" style={{ marginTop: '1.5rem' }}>{error}</div>}
            <ManualEntryPanel
              manualForm={manualForm}
              setManualForm={setManualForm}
              markupPct={markupPct}
              setMarkupPct={setMarkupPct}
              onSubmit={handleManualEntry}
              onBack={() => setShowManualEntry(false)}
              loading={loading}
            />
          </>
        ) : (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <div className="card-body">
            {/* Drop zone */}
            <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragover' : ''}`}>
              <input {...getInputProps()} />
              <div className="upload-icon"><Upload size={22} /></div>
              <p className="upload-title">Drop drawing PDFs here or click to browse</p>
              <p className="upload-subtitle">PDF, PNG, JPG, DOCX, XLSX, TXT — up to 100 MB each</p>
              <div className="upload-types">
                {['PDF', 'PNG', 'JPG', 'DOCX', 'XLSX', 'TXT'].map(t => (
                  <span key={t} className="upload-type-badge">{t}</span>
                ))}
              </div>
            </div>

            {/* File list */}
            {files.length > 0 && (
              <div className="file-list">
                {files.map((f, i) => {
                  const ext = getFileExt(f.name)
                  return (
                    <div key={i} className="file-item">
                      <div className={`file-icon ${fileIconClass(ext)}`}>{ext.toUpperCase().slice(0, 3)}</div>
                      <div className="file-info">
                        <div className="file-name">{f.name}</div>
                        <div className="file-size">{(f.size / 1024 / 1024).toFixed(1)} MB</div>
                      </div>
                      <button className="btn btn-ghost btn-sm" onClick={() => removeFile(i)}>Remove</button>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Markup */}
            <div className="form-group" style={{ marginTop: '1.25rem', maxWidth: 200 }}>
              <label className="form-label">Markup %</label>
              <input
                type="number" min={0} max={80} value={markupPct}
                onChange={e => setMarkupPct(Number(e.target.value))}
                className="form-input"
              />
            </div>

            {/* Processing progress */}
            {loading && (
              <div className="alert alert-info" style={{ marginTop: '1.25rem' }}>
                <p style={{ fontWeight: 600, marginBottom: '0.875rem' }}>Processing drawing package…</p>
                <ProcessingProgress steps={processingSteps} />
                <p style={{ marginTop: '0.875rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Check the browser console (F12) for detailed logs.
                </p>
              </div>
            )}

            {error && (
              <div className="alert alert-error" style={{ marginTop: '1rem' }}>
                <span>{error}</span>
                {!showManualEntry && (
                  <button className="btn btn-primary btn-sm" style={{ marginLeft: '0.75rem' }} onClick={() => setShowManualEntry(true)}>
                    Enter Details Manually
                  </button>
                )}
              </div>
            )}

            <button
              className="btn btn-primary btn-lg"
              style={{ width: '100%', marginTop: '1.25rem' }}
              onClick={handleAnalyse}
              disabled={!files.length || loading}
            >
              {loading
                ? <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} /> Analysing…</>
                : <><Upload size={16} /> Analyse Drawings</>
              }
            </button>
          </div>
        </div>
        )}
      </div>
    )
  }

  // ── REVIEW SCREEN ──────────────────────────────────────────────
  const reviewCount = result.bom_items.filter(i => i.review_required).length
  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'bom',     label: 'BOM Items',  count: result.bom_items.length },
    { id: 'costing', label: 'Customer Information' },
    { id: 'summary', label: 'Summary' },
  ]

  return (
    <div className="page-body" style={{ maxWidth: 1200, margin: '0 auto', padding: '1rem 1.5rem' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
        <div>
          <h1 className="page-title">Drawing Review — {result.job_number}</h1>
          <p className="page-subtitle">
            {result.bom_items.length} BOM items · {fmt(result.total_steel_kg, 1)} kg steel
            {reviewCount > 0 && (
              <span style={{ color: 'var(--warning-600)', marginLeft: '0.5rem', fontWeight: 600 }}>
                · {reviewCount} items need review
              </span>
            )}
            {result.project_information?.drawing_number && (
              <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                · Dwg: {result.project_information.drawing_number}
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {jobId && (
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/history')}>
              ← Job History
            </button>
          )}
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => { navigate('/drawing-costing'); setResult(null); setFiles([]); setProcessingStep(0) }}
          >
            ← New Analysis
          </button>
        </div>
      </div>

      {/* Confidence strip */}
      <div style={{
        display: 'flex', gap: '1rem', alignItems: 'center',
        padding: '0.6rem 1rem', background: 'var(--gray-50)',
        borderRadius: 'var(--radius-md)', border: '1px solid var(--border)',
        marginBottom: '1rem', fontSize: '0.82rem',
      }}>
        <span style={{ color: 'var(--text-muted)' }}>Extraction confidence:</span>
        <ConfidencePill value={result.overall_confidence} />
        <span style={{ color: 'var(--text-muted)', marginLeft: 'auto', fontStyle: 'italic', maxWidth: 500, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
          {result.summary}
        </span>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '0.75rem' }}>{error}</div>}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '0.625rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <button className="btn btn-success" onClick={handleGenerateExcel} disabled={exporting}>
          <FileSpreadsheet size={14} /> {exporting ? 'Generating…' : 'Generate Excel'}
        </button>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`tab${activeTab === t.id ? ' active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
            {t.count !== undefined && (
              <span style={{
                marginLeft: '0.375rem', padding: '0.1rem 0.4rem',
                background: 'var(--gray-100)', borderRadius: 'var(--radius-full)',
                fontSize: '0.7rem', color: 'var(--text-muted)',
              }}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── BOM Items tab ── */}
      {activeTab === 'bom' && (
        <>
          {result.bom_items.length === 0 ? (
            <>
              <div className="alert alert-warning" style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                <AlertTriangle size={16} />
                <span>No quantities were extracted from this document.</span>
                <button className="btn btn-primary btn-sm" onClick={() => setShowManualEntry(true)}>
                  Enter Details Manually
                </button>
              </div>
              {showManualEntry && (
                <ManualEntryPanel
                  manualForm={manualForm}
                  setManualForm={setManualForm}
                  markupPct={markupPct}
                  setMarkupPct={setMarkupPct}
                  onSubmit={handleManualEntry}
                  onBack={() => setShowManualEntry(false)}
                  loading={loading}
                />
              )}
            </>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Description</th>
                    <th>Category</th>
                    <th>Section</th>
                    <th>Qty</th>
                    <th>Length (mm)</th>
                    <th>Unit Wt (kg/m)</th>
                    <th>Total Wt (kg)</th>
                    <th>Grade</th>
                    <th>Confidence</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {result.bom_items.map((item, i) => (
                    <tr
                      key={item.id}
                      style={item.review_required ? { background: 'var(--warning-50)' } : {}}
                    >
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{i + 1}</td>
                      <td>
                        <input
                          defaultValue={item.description}
                          onBlur={e => handleBomEdit(item.id, 'description', e.target.value)}
                          style={{ width: 200, fontSize: '0.8rem', padding: '0.25rem 0.4rem', border: '1px solid transparent', borderRadius: 4, background: 'transparent' }}
                          onFocus={e => (e.target.style.borderColor = 'var(--primary-400)')}
                        />
                      </td>
                      <td style={{ fontSize: '0.75rem' }}>{item.category}</td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{item.section_size || '—'}</td>
                      <td>
                        <input
                          type="number"
                          defaultValue={item.qty ?? ''}
                          placeholder="—"
                          onBlur={e => handleBomEdit(item.id, 'qty', e.target.value ? Number(e.target.value) : null)}
                          style={{ width: 55, fontSize: '0.8rem', padding: '0.25rem 0.4rem', border: '1px solid transparent', borderRadius: 4, background: 'transparent' }}
                          onFocus={e => (e.target.style.borderColor = 'var(--primary-400)')}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          defaultValue={item.length_mm ?? ''}
                          placeholder="—"
                          onBlur={e => handleBomEdit(item.id, 'length_mm', e.target.value ? Number(e.target.value) : null)}
                          style={{ width: 80, fontSize: '0.8rem', padding: '0.25rem 0.4rem', border: '1px solid transparent', borderRadius: 4, background: 'transparent' }}
                          onFocus={e => (e.target.style.borderColor = 'var(--primary-400)')}
                        />
                      </td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{fmt(item.unit_weight_kg)}</td>
                      <td>
                        <input
                          type="number"
                          defaultValue={item.total_weight_kg ?? ''}
                          placeholder="—"
                          onBlur={e => handleBomEdit(item.id, 'total_weight_kg', e.target.value ? Number(e.target.value) : null)}
                          style={{ width: 80, fontSize: '0.8rem', padding: '0.25rem 0.4rem', border: '1px solid transparent', borderRadius: 4, background: 'transparent' }}
                          onFocus={e => (e.target.style.borderColor = 'var(--primary-400)')}
                        />
                      </td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{item.material_grade || '—'}</td>
                      <td><ConfidencePill value={item.confidence} /></td>
                      <td>
                        {item.review_required && <span className="badge badge-warning">⚠ Review</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Costing tab ── */}
      {activeTab === 'costing' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginTop: '0.5rem' }}>

          {/* Customer + markup form */}
          <div className="card">
            <div className="card-header"><h3 className="card-title">Customer Information</h3></div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {Object.entries(customer).map(([k, v]) => (
                <div key={k} className="form-group">
                  <label className="form-label">{k.replace(/([A-Z])/g, ' $1').trim()}</label>
                  <input
                    className="form-input" value={v}
                    onChange={e => setCustomer(prev => ({ ...prev, [k]: e.target.value }))}
                  />
                </div>
              ))}
              <div className="form-group">
                <label className="form-label">Markup %</label>
                <input
                  type="number" min={0} max={80} className="form-input" value={markupPct}
                  onChange={e => setMarkupPct(Number(e.target.value))}
                />
              </div>
              <button className="btn btn-secondary btn-sm" onClick={handleRecalculate} disabled={loading}>
                <RefreshCw size={13} /> Apply Markup
              </button>
            </div>
          </div>

          {/* Cost breakdown */}
          <div className="card">
            <div className="card-header"><h3 className="card-title">Cost Breakdown</h3></div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {[
                { label: 'Total Steel',         value: `${fmt(result.costing.total_steel_kg)} kg` },
                { label: 'Steel Material',       value: aed(result.costing.steel_mat_cost) },
                { label: 'Bolts',                value: aed(result.costing.bolt_cost) },
                { label: 'Paint Material',       value: aed(result.costing.paint_mat_cost) },
                { label: 'Welding Labour',       value: aed(result.costing.weld_cost) },
                { label: 'Fabrication Labour',   value: aed(result.costing.fab_cost) },
                { label: 'Blasting',             value: aed(result.costing.blast_cost) },
                { label: 'Painting',             value: aed(result.costing.paint_app_cost) },
                { label: 'MPI / Inspection',     value: aed(result.costing.mpi_cost) },
                { label: 'QA/QC',                value: aed(result.costing.qaqc_cost) },
                { label: 'Packing & Loading',    value: aed(result.costing.packing_cost) },
              ].map(({ label, value }) => (
                <div key={label} className="cost-row">
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.83rem' }}>{label}</span>
                  <span style={{ fontSize: '0.83rem' }}>{value}</span>
                </div>
              ))}

              <hr style={{ margin: '0.5rem 0', borderColor: 'var(--border)' }} />

              {[
                { label: 'Subtotal',     value: aed(result.costing.subtotal),    bold: false },
                { label: 'Overhead',     value: aed(result.costing.overhead),    bold: false },
                { label: 'Consumables',  value: aed(result.costing.consumables), bold: false },
                { label: 'Grand Total',  value: aed(result.costing.grand_total), bold: true  },
              ].map(({ label, value, bold }) => (
                <div key={label} className="cost-row">
                  <span style={{ fontWeight: bold ? 700 : 400, fontSize: '0.83rem' }}>{label}</span>
                  <span style={{ fontWeight: bold ? 700 : 400, fontSize: '0.83rem' }}>{value}</span>
                </div>
              ))}

              <div className="cost-row" style={{
                background: 'var(--primary-50)', padding: '0.6rem 0.75rem',
                borderRadius: 'var(--radius-md)', border: '1px solid var(--primary-200)',
                marginTop: '0.25rem',
              }}>
                <span style={{ fontWeight: 800, color: 'var(--primary-800)' }}>Selling Price</span>
                <span style={{ fontWeight: 800, color: 'var(--primary-800)', fontSize: '1.1rem' }}>
                  {aed(result.costing.selling_price)}
                </span>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem', textAlign: 'right' }}>
                Profit: {aed(result.costing.net_profit)} ({fmt(result.costing.profit_pct, 1)}%) · Markup: {fmt(result.costing.markup_pct, 1)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Summary tab ── */}
      {activeTab === 'summary' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>

          {/* Extraction summary */}
          <div className="card">
            <div className="card-header"><h3 className="card-title">Extraction Summary</h3></div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {result.summary || 'No summary available.'}
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.5rem' }}>
                {[
                  { label: 'BOM Items',        value: String(result.bom_items.length) },
                  { label: 'Total Steel',       value: `${fmt(result.total_steel_kg, 1)} kg` },
                  { label: 'Confidence',        value: result.overall_confidence != null ? `${Math.round(result.overall_confidence * 100)}%` : '—' },
                  { label: 'Need Review',       value: String(reviewCount) },
                  { label: 'Selling Price',     value: aed(result.costing.selling_price) },
                ].map(({ label, value }) => (
                  <div key={label} style={{ padding: '0.75rem', background: 'var(--gray-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '0.2rem', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{label}</p>
                    <p style={{ fontSize: '1rem', fontWeight: 700 }}>{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Project info */}
          {(result.project_information?.project_name || result.project_information?.client_name || result.project_information?.drawing_number) && (
            <div className="card">
              <div className="card-header"><h3 className="card-title">Project Information</h3></div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {[
                  { label: 'Project Name',   value: result.project_information.project_name },
                  { label: 'Client',         value: result.project_information.client_name },
                  { label: 'Drawing Number', value: result.project_information.drawing_number },
                ].filter(r => r.value).map(({ label, value }) => (
                  <div key={label} className="cost-row">
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.83rem' }}>{label}</span>
                    <span style={{ fontSize: '0.83rem' }}>{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Flags */}
          {result.flags?.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title" style={{ color: 'var(--warning-700)' }}>
                  ⚠ Ambiguities & Flags ({result.flags.length})
                </h3>
              </div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {result.flags.map((f, i) => (
                  <div key={i} className="alert alert-warning" style={{ padding: '0.5rem 0.75rem', fontSize: '0.82rem' }}>
                    <strong>{f.field}:</strong> {f.message}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Customer information modal — required before generating the costing sheet */}
      {showCustomerModal && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: '1rem',
          }}
          onClick={() => !exporting && setShowCustomerModal(false)}
        >
          <div
            className="card"
            style={{ maxWidth: 480, width: '100%', maxHeight: '90vh', overflowY: 'auto' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="card-header">
              <h3 className="card-title">Customer Information</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
                Required before generating the costing sheet — saved to this job for next time.
              </p>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {Object.entries(customer).map(([k, v]) => (
                <div key={k} className="form-group">
                  <label className="form-label">
                    {k.replace(/([A-Z])/g, ' $1').trim()}{k === 'customerName' && ' *'}
                  </label>
                  <input
                    className="form-input" value={v}
                    onChange={e => setCustomer(prev => ({ ...prev, [k]: e.target.value }))}
                  />
                </div>
              ))}
              {error && <div className="alert alert-error">{error}</div>}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.625rem', marginTop: '0.5rem' }}>
                <button className="btn btn-ghost" onClick={() => setShowCustomerModal(false)} disabled={exporting}>
                  Cancel
                </button>
                <button
                  className="btn btn-success"
                  onClick={doGenerateExcel}
                  disabled={exporting || !customer.customerName.trim()}
                >
                  <FileSpreadsheet size={14} /> {exporting ? 'Generating…' : 'Confirm & Generate'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
