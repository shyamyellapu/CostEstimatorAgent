import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import { Upload, FileText, Image, File, X, ChevronRight, AlertTriangle, CheckCircle, Edit3, Loader } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

type Step = 'upload' | 'extract' | 'confirm' | 'calculate'

interface UploadedFile { file: File; id?: string }
interface ExtractedItem {
  item_tag: string; description: string; section_type: string
  quantity: number; length_mm: number | null; width_mm: number | null
  thickness_mm: number | null; od_mm: number | null; material_grade: string | null
  weld_joints: number | null; confidence: number; flags: any[]
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'pdf') return { label: 'PDF', cls: 'pdf' }
  if (['png','jpg','jpeg'].includes(ext || '')) return { label: 'IMG', cls: 'img' }
  if (['xlsx','xls'].includes(ext || '')) return { label: 'XLS', cls: 'xlsx' }
  if (['docx','doc'].includes(ext || '')) return { label: 'DOC', cls: 'docx' }
  return { label: 'FILE', cls: 'other' }
}

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024*1024) return `${(b/1024).toFixed(1)} KB`
  return `${(b/1024/1024).toFixed(1)} MB`
}

export default function NewEstimate() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('upload')
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobNumber, setJobNumber] = useState('')
  const [clientName, setClientName] = useState('')
  const [projectName, setProjectName] = useState('')
  const [projectRef, setProjectRef] = useState('')
  const [loading, setLoading] = useState(false)
  const [extractions, setExtractions] = useState<any[]>([])
  const [confirmedItems, setConfirmedItems] = useState<ExtractedItem[]>([])
  const [costResult, setCostResult] = useState<any>(null)
  const [excelDownloading, setExcelDownloading] = useState(false)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: useCallback((accepted: File[]) => {
      setFiles(prev => [...prev, ...accepted.map(f => ({ file: f }))])
    }, []),
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxSize: 50 * 1024 * 1024,
  })

  const removeFile = (i: number) => setFiles(f => f.filter((_, idx) => idx !== i))

  // Step 1: Upload
  const handleUpload = async () => {
    if (!files.length) { toast.error('Please add at least one file'); return }
    setLoading(true)
    try {
      const fd = new FormData()
      files.forEach(f => fd.append('files', f.file))
      if (clientName) fd.append('client_name', clientName)
      if (projectName) fd.append('project_name', projectName)
      if (projectRef) fd.append('project_ref', projectRef)
      const res = await api.post('/estimate/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setJobId(res.data.job_id)
      setJobNumber(res.data.job_number)
      toast.success(`Job ${res.data.job_number} created — ${res.data.uploaded_files.length} file(s) uploaded`)
      setStep('extract')
    } catch (e: any) { toast.error(e.message) }
    finally { setLoading(false) }
  }

  // Step 2: Extract
  const handleExtract = async () => {
    if (!jobId) return
    setLoading(true)
    try {
      const res = await api.post(`/estimate/extract?job_id=${jobId}`)
      setExtractions(res.data.extractions)
      // Flatten all dimension items for confirmation
      const allItems: ExtractedItem[] = []
      for (const ext of res.data.extractions) {
        const dims = ext.data?.dimensions || []
        allItems.push(...dims)
      }
      setConfirmedItems(allItems)
      toast.success(`Extraction complete — ${allItems.length} items found`)
      setStep('confirm')
    } catch (e: any) { toast.error(e.message) }
    finally { setLoading(false) }
  }

  // Step 3: Confirm
  const handleConfirm = async () => {
    if (!jobId) return
    if (!confirmedItems.length) { toast.error('No items to confirm'); return }
    setLoading(true)
    try {
      await api.post(`/estimate/confirm?job_id=${jobId}`, confirmedItems)
      toast.success('Data confirmed — running costing engine…')
      const res2 = await api.post(`/estimate/calculate?job_id=${jobId}`)
      setCostResult(res2.data)
      setStep('calculate')
      toast.success('Costing complete!')
    } catch (e: any) { toast.error(e.message) }
    finally { setLoading(false) }
  }

  // Download Excel
  const downloadExcel = async () => {
    if (!jobId) return
    setExcelDownloading(true)
    try {
      const res = await api.post(`/estimate/generate-excel?job_id=${jobId}`, {}, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url
      a.download = `${jobNumber}_costing_sheet.xlsx`; a.click()
      URL.revokeObjectURL(url)
      toast.success('Excel downloaded!')
    } catch (e: any) { toast.error(e.message) }
    finally { setExcelDownloading(false) }
  }

  const stepList: { key: Step; label: string }[] = [
    { key: 'upload', label: 'Upload Files' },
    { key: 'extract', label: 'AI Extraction' },
    { key: 'confirm', label: 'Confirm Data' },
    { key: 'calculate', label: 'Cost Summary' },
  ]
  const stepIdx = stepList.findIndex(s => s.key === step)

  return (
    <div className="animate-fade-in" style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">New Estimate</h1>
          <p className="page-subtitle">Upload drawings, BOQs, or images to generate a cost estimate</p>
        </div>
        {jobNumber && <span className="badge badge-primary" style={{ fontSize: '0.8rem', padding: '0.3rem 0.75rem' }}>{jobNumber}</span>}
      </div>

      {/* Stepper */}
      <div className="steps mb-6">
        {stepList.map((s, i) => (
          <div key={s.key} style={{ display: 'flex', alignItems: 'center', flex: i < stepList.length - 1 ? 1 : 'none' }}>
            <div className={`step${i === stepIdx ? ' active' : ''}${i < stepIdx ? ' done' : ''}`}>
              <div className="step-num">{i < stepIdx ? '✓' : i + 1}</div>
              {s.label}
            </div>
            {i < stepList.length - 1 && <div className={`step-connector${i < stepIdx ? ' done' : ''}`} />}
          </div>
        ))}
      </div>

      {/* ── STEP: UPLOAD ── */}
      {step === 'upload' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Job Info */}
          <div className="card">
            <div className="card-header"><div className="card-title">Job Information</div></div>
            <div className="card-body">
              <div className="grid grid-cols-2 gap-4">
                <div className="form-group">
                  <label className="form-label">Client Name</label>
                  <input className="form-input" placeholder="e.g. ADNOC, Samsung" value={clientName} onChange={e => setClientName(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Project Name</label>
                  <input className="form-input" placeholder="e.g. Pipe Rack Fabrication" value={projectName} onChange={e => setProjectName(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Reference No.</label>
                  <input className="form-input" placeholder="e.g. RFQ-2024-001" value={projectRef} onChange={e => setProjectRef(e.target.value)} />
                </div>
              </div>
            </div>
          </div>

          {/* Dropzone */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Upload Documents</div>
                <div className="card-subtitle">Supports PDF, images (PNG/JPG), Excel, and DOCX files</div>
              </div>
            </div>
            <div className="card-body">
              <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragover' : ''}`}>
                <input {...getInputProps()} />
                <div className="upload-icon"><Upload size={22} /></div>
                <div className="upload-title">Drop files here or click to browse</div>
                <div className="upload-subtitle">Max 50 MB per file</div>
                <div className="upload-types">
                  {['PDF','PNG','JPG','XLSX','DOCX'].map(t => <span key={t} className="upload-type-badge">{t}</span>)}
                </div>
              </div>
              {files.length > 0 && (
                <div className="file-list">
                  {files.map((f, i) => {
                    const ic = fileIcon(f.file.name)
                    return (
                      <div key={i} className="file-item">
                        <div className={`file-icon ${ic.cls}`}>{ic.label}</div>
                        <div className="file-info">
                          <div className="file-name">{f.file.name}</div>
                          <div className="file-size">{formatBytes(f.file.size)}</div>
                        </div>
                        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => removeFile(i)}>
                          <X size={14} />
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
            <div className="card-footer" style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" onClick={handleUpload} disabled={loading || !files.length}>
                {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Uploading…</> : <>Upload & Continue <ChevronRight size={16} /></>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── STEP: EXTRACT ── */}
      {step === 'extract' && (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">AI Extraction</div>
              <div className="card-subtitle">The AI will read all uploaded files and extract dimensions, materials, and fabrication data</div>
            </div>
          </div>
          <div className="card-body">
            <div className="alert alert-info" style={{ marginBottom: '1.25rem' }}>
              <AlertTriangle size={16} />
              <div>
                <strong>Review Required: </strong>
                After extraction, you must review and confirm all extracted data before costing begins. Low-confidence items will be flagged.
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {files.map((f, i) => (
                <div key={`${f.file.name}-${i}`} className="file-item">
                  <div className={`file-icon ${fileIcon(f.file.name).cls}`}>{fileIcon(f.file.name).label}</div>
                  <div className="file-info">
                    <div className="file-name">{f.file.name}</div>
                    <div className="file-size">Queued for extraction</div>
                  </div>
                  <span className="badge badge-warning">Queued</span>
                </div>
              ))}
            </div>
          </div>
          <div className="card-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button className="btn btn-secondary" onClick={() => setStep('upload')}>Back</button>
            <button className="btn btn-primary" onClick={handleExtract} disabled={loading}>
              {loading
                ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Extracting…</>
                : <>Start AI Extraction <ChevronRight size={16} /></>}
            </button>
          </div>
        </div>
      )}

      {/* ── STEP: CONFIRM ── */}
      {step === 'confirm' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="alert alert-warning">
            <AlertTriangle size={16} />
            <span>Review all extracted items below. Edit any incorrect values before confirming. Items with low confidence are highlighted.</span>
          </div>

          {confirmedItems.map((item, i) => (
            <ExtractedItemCard
              key={`${item.item_tag}-${i}`}
              item={item}
              onChange={updated => setConfirmedItems(prev => prev.map((x, idx) => idx === i ? updated : x))}
            />
          ))}

          {confirmedItems.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <h3>No items extracted</h3>
              <p>The AI couldn't find structured dimension data. Try adding more context or a clearer drawing.</p>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button className="btn btn-secondary" onClick={() => setStep('extract')}>Re-extract</button>
            <button className="btn btn-primary" onClick={handleConfirm} disabled={loading || !confirmedItems.length}>
              {loading
                ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Calculating…</>
                : <>Confirm & Calculate <ChevronRight size={16} /></>}
            </button>
          </div>
        </div>
      )}

      {/* ── STEP: RESULTS ── */}
      {step === 'calculate' && costResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="alert alert-success">
            <CheckCircle size={16} />
            <span>Costing complete for job <strong>{jobNumber}</strong>. Review summary below and download the Excel sheet.</span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="card">
              <div className="card-header"><div className="card-title">Cost Breakdown</div></div>
              <div className="card-body">
                {[
                  ['Total Weight', `${(costResult.totals.total_weight_kg || 0).toFixed(2)} kg`],
                  ['Material Cost', fmt(costResult.totals.total_material_cost)],
                  ['Fabrication Cost', fmt(costResult.totals.total_fabrication_cost)],
                  ['Welding Cost', fmt(costResult.totals.total_welding_cost)],
                  ['Consumables', fmt(costResult.totals.total_consumables_cost)],
                  ['Cutting', fmt(costResult.totals.total_cutting_cost)],
                  ['Surface Treatment', fmt(costResult.totals.total_surface_treatment_cost)],
                ].map(([l, v]) => (
                  <div key={l} className="cost-row"><span className="cost-label">{l}</span><span className="cost-value">{v}</span></div>
                ))}
                <div className="cost-row" style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 4 }}>
                  <span className="cost-label font-semibold">Direct Cost</span>
                  <span className="cost-value">{fmt(costResult.totals.total_direct_cost)}</span>
                </div>
                <div className="cost-row">
                  <span className="cost-label">Overhead ({costResult.totals.overhead_percentage}%)</span>
                  <span className="cost-value">{fmt(costResult.totals.overhead_cost)}</span>
                </div>
                <div className="cost-row total">
                  <span>SELLING PRICE</span>
                  <span>{fmt(costResult.totals.selling_price)}</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="card">
                <div className="card-body" style={{ textAlign: 'center', padding: '1.5rem' }}>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 8 }}>TOTAL SELLING PRICE</div>
                  <div style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--primary-700)', letterSpacing: '-0.05em' }}>
                    {fmt(costResult.totals.selling_price)}
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: 4 }}>AED (Ex-Works)</div>
                </div>
              </div>
              <button className="btn btn-success btn-lg" onClick={downloadExcel} disabled={excelDownloading} style={{ width: '100%' }}>
                {excelDownloading ? <><span className="spinner" style={{ width: 18, height: 18 }} /> Generating…</> : '⬇  Download Excel Costing Sheet'}
              </button>
              <button className="btn btn-secondary" onClick={() => navigate('/cover-letter')} style={{ width: '100%' }}>
                Generate Cover Letter →
              </button>
              <button className="btn btn-ghost" onClick={() => navigate('/history')} style={{ width: '100%' }}>
                View Job History
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function fmt(v?: number) {
  if (v == null) return '—'
  return `AED ${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function ExtractedItemCard({ item, onChange }: { item: ExtractedItem; onChange: (i: ExtractedItem) => void }) {
  const conf = item.confidence
  const confClass = conf >= 0.8 ? 'conf-high' : conf >= 0.5 ? 'conf-medium' : 'conf-low'
  const isLow = conf < 0.5

  return (
    <div className={`extraction-item${isLow ? ' flagged' : ''}`}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
            {item.item_tag || 'Item'}
          </span>
          <span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>{item.section_type}</span>
          {isLow && <span className="badge badge-warning">⚠ Low Confidence</span>}
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
          {(conf * 100).toFixed(0)}%
          <div className="confidence-bar" style={{ width: 60 }}>
            <div className={`confidence-fill ${confClass}`} style={{ width: `${conf * 100}%` }} />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Description', key: 'description', span: 4 },
          { label: 'Section Type', key: 'section_type' },
          { label: 'Qty', key: 'quantity' },
          { label: 'Length (mm)', key: 'length_mm' },
          { label: 'Width (mm)', key: 'width_mm' },
          { label: 'Thickness (mm)', key: 'thickness_mm' },
          { label: 'OD (mm)', key: 'od_mm' },
          { label: 'Material Grade', key: 'material_grade' },
          { label: 'Weld Joints', key: 'weld_joints' },
        ].map(f => (
          <div key={f.key} className="form-group" style={f.span ? { gridColumn: `span ${f.span}` } : {}}>
            <label className="form-label" style={{ fontSize: '0.7rem' }}>{f.label}</label>
            <input
              className="form-input"
              style={{ fontSize: '0.8125rem', padding: '0.375rem 0.625rem' }}
              value={(item as any)[f.key] ?? ''}
              onChange={e => onChange({ ...item, [f.key]: e.target.value })}
            />
          </div>
        ))}
      </div>
      {item.flags?.length > 0 && (
        <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {item.flags.map((fl, i) => (
            <div key={i} style={{ fontSize: '0.75rem', color: 'var(--warning-600)', display: 'flex', gap: 4 }}>
              <AlertTriangle size={12} style={{ flexShrink: 0, marginTop: 2 }} />
              <span><strong>{fl.field}:</strong> {fl.reason}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
