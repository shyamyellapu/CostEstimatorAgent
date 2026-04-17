import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import { Upload, X, ChevronRight, AlertTriangle, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

type Step = 'upload' | 'extract' | 'confirm' | 'calculate'

interface UploadedFile { file: File; id?: string }

// ── Rich extraction types (same as DrawingReader) ──────────────────────────
interface DrawingMetadata {
  project_name?: string; unit_area?: string; drawing_number?: string; revision?: string
  client?: string; consultant?: string; contractor?: string; work_order_number?: string
  scale?: string; date_issued?: string; referenced_drawings?: string[]; general_notes?: string[]
}
interface StructuralElement {
  support_tag?: string; item_description?: string; section_type?: string
  section_designation?: string; material_grade?: string
  length_mm?: number | null; width_mm?: number | null; thickness_mm?: number | null
  quantity?: number | null; unit_weight_kg_per_m?: number | null; total_weight_kg?: number | null
  weld_type?: string; weld_size_mm?: number | null; weld_length_mm?: number | null
  surface_area_m2?: number | null; notes?: string
}
interface BoltPlateItem {
  item_description?: string; size_designation?: string; grade?: string
  length_mm?: number | null; quantity?: number | null; notes?: string
}
interface SurfaceTreatment {
  blasting_standard?: string; paint_system?: string; galvanizing_required?: boolean
  galvanized_members?: string[]; total_surface_area_m2?: number | null
}
interface WeightSummary {
  total_structural_steel_kg?: number | null; total_plates_kg?: number | null; grand_total_steel_kg?: number | null
}
interface AmbiguityItem { location?: string; issue?: string; assumption_made?: string }
interface FlagItem { field?: string; reason?: string }
interface ExtractionResult {
  drawing_metadata?: DrawingMetadata | null
  structural_elements?: StructuralElement[]
  bolts_and_plates?: BoltPlateItem[]
  surface_treatment?: SurfaceTreatment | null
  weight_summary?: WeightSummary | null
  ambiguities?: AmbiguityItem[]
  flags?: FlagItem[]
  dimensions?: any[]
  summary?: string
  overall_confidence?: number
  member_types?: string[]
  material_references?: string[]
  annotations?: string[]
  fabrication_notes?: string[]
}
interface FileExtraction {
  file_id: string; filename: string; confidence: number
  data?: ExtractionResult; error?: string
}
// Flat item for costing engine
interface CostingItem {
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
function fmtVal(v?: number | string | null) { return (v == null || v === '') ? '—' : v }
function hasMetaData(m: DrawingMetadata) { return Object.values(m).some(v => Array.isArray(v) ? v.length > 0 : Boolean(v)) }

// Convert rich StructuralElement → flat CostingItem for the costing engine
function toCostingItems(data: ExtractionResult): CostingItem[] {
  const items: CostingItem[] = []
  for (const el of data.structural_elements || []) {
    items.push({
      item_tag: el.support_tag || '',
      description: el.item_description || '',
      section_type: el.section_type || '',
      quantity: el.quantity ?? 1,
      length_mm: el.length_mm ?? null,
      width_mm: el.width_mm ?? null,
      thickness_mm: el.thickness_mm ?? null,
      od_mm: null,
      material_grade: el.material_grade ?? null,
      weld_joints: el.weld_length_mm ?? null,
      confidence: 0.9,
      flags: [],
    })
  }
  // fallback to legacy dimensions
  if (items.length === 0) {
    for (const d of data.dimensions || []) {
      items.push({
        item_tag: d.item_tag || '',
        description: d.description || '',
        section_type: d.section_type || '',
        quantity: d.quantity ?? 1,
        length_mm: d.length_mm ?? null,
        width_mm: d.width_mm ?? null,
        thickness_mm: d.thickness_mm ?? null,
        od_mm: d.od_mm ?? null,
        material_grade: d.material_grade ?? null,
        weld_joints: d.weld_joints ?? null,
        confidence: d.confidence ?? 0.5,
        flags: d.flags || [],
      })
    }
  }
  return items
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
  const [extractions, setExtractions] = useState<FileExtraction[]>([])
  const [confirmedItems, setConfirmedItems] = useState<CostingItem[]>([])
  const [costResult, setCostResult] = useState<any>(null)
  const [excelDownloading, setExcelDownloading] = useState(false)
  const [expandedFiles, setExpandedFiles] = useState<Record<string, boolean>>({})
  const [editMode, setEditMode] = useState(false)

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
      const richExtractions: FileExtraction[] = res.data.extractions
      setExtractions(richExtractions)
      // Auto-expand all files
      const expanded: Record<string, boolean> = {}
      for (const e of richExtractions) expanded[e.file_id] = true
      setExpandedFiles(expanded)
      // Build flat costing items from all successful extractions
      const allItems: CostingItem[] = []
      for (const ext of richExtractions) {
        if (ext.data) allItems.push(...toCostingItems(ext.data))
      }
      setConfirmedItems(allItems)
      const totalItems = allItems.length
      toast.success(`Extraction complete — ${totalItems} items found across ${richExtractions.length} file(s)`)
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
    <div className="animate-fade-in" style={{ maxWidth: 1100, margin: '0 auto' }}>
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

          {/* Summary bar */}
          <div className="card animate-fade-in">
            <div className="card-header">
              <div>
                <div className="card-title">Extraction Complete</div>
                <div className="card-subtitle">{extractions.length} file(s) processed — review and confirm before costing</div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <span className="badge badge-neutral">{confirmedItems.length} items</span>
                <button className="btn btn-secondary btn-sm" onClick={() => setEditMode(e => !e)}>
                  {editMode ? 'Hide Edit' : 'Edit Items'}
                </button>
              </div>
            </div>
          </div>

          {/* Per-file rich extraction panels */}
          {extractions.map(ext => {
            const d = ext.data
            const conf = Math.round((ext.confidence || 0) * 100)
            const isExpanded = expandedFiles[ext.file_id] !== false
            const ic = fileIcon(ext.filename)
            return (
              <div key={ext.file_id} className="card animate-fade-in">
                {/* File header — click to collapse */}
                <div
                  className="card-header"
                  style={{ cursor: 'pointer', userSelect: 'none' }}
                  onClick={() => setExpandedFiles(prev => ({ ...prev, [ext.file_id]: !isExpanded }))}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                    <div className={`file-icon ${ic.cls}`} style={{ width: 32, height: 32, fontSize: '0.6rem' }}>{ic.label}</div>
                    <div>
                      <div className="card-title" style={{ fontSize: '0.9rem' }}>{ext.filename}</div>
                      {d?.drawing_metadata?.project_name && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{d.drawing_metadata.project_name}</div>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                    {ext.error
                      ? <span className="badge badge-warning">Failed</span>
                      : <span className={`badge ${conf >= 70 ? 'badge-success' : 'badge-warning'}`}>{conf}% confidence</span>}
                    {d?.member_types?.map((t, i) => <span key={i} className="badge badge-primary" style={{ fontSize: '0.65rem' }}>{t}</span>)}
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </div>

                {isExpanded && d && !ext.error && (
                  <div style={{ padding: '0 1rem 1rem' }}>

                    {/* Summary text */}
                    {d.summary && <p style={{ fontSize: '0.875rem', margin: '0.5rem 0 1rem', color: 'var(--text-secondary)' }}>{d.summary}</p>}

                    {/* Metadata + Surface/Weight row */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                      {d.drawing_metadata && hasMetaData(d.drawing_metadata) && (
                        <div style={{ background: 'var(--bg-secondary)', borderRadius: 10, padding: '0.875rem' }}>
                          <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.625rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Drawing Metadata</div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem 1.25rem', fontSize: '0.8125rem' }}>
                            {[
                              ['Project', d.drawing_metadata.project_name], ['Unit / Area', d.drawing_metadata.unit_area],
                              ['Drawing No.', d.drawing_metadata.drawing_number], ['Revision', d.drawing_metadata.revision],
                              ['Client', d.drawing_metadata.client], ['Contractor', d.drawing_metadata.contractor],
                              ['Work Order', d.drawing_metadata.work_order_number], ['Scale', d.drawing_metadata.scale],
                            ].map(([label, val]) => val ? (
                              <div key={label}>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{label}</div>
                                <div style={{ fontWeight: 600 }}>{val}</div>
                              </div>
                            ) : null)}
                          </div>
                          {d.drawing_metadata.referenced_drawings && d.drawing_metadata.referenced_drawings.length > 0 && (
                            <div style={{ marginTop: '0.625rem' }}>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>Referenced Drawings</div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                                {d.drawing_metadata.referenced_drawings.map((r, i) => <span key={i} className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>{r}</span>)}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {d.weight_summary && (d.weight_summary.grand_total_steel_kg || d.weight_summary.total_structural_steel_kg) && (
                          <div style={{ background: 'var(--bg-secondary)', borderRadius: 10, padding: '0.875rem' }}>
                            <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.625rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Weight Summary</div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
                              {[
                                ['Structural', d.weight_summary.total_structural_steel_kg],
                                ['Plates', d.weight_summary.total_plates_kg],
                                ['Total', d.weight_summary.grand_total_steel_kg],
                              ].map(([label, val]) => (
                                <div key={label as string} style={{ textAlign: 'center', background: label === 'Total' ? 'var(--accent-primary)' : 'var(--bg-card)', borderRadius: 8, padding: '0.5rem' }}>
                                  <div style={{ fontSize: '0.65rem', color: label === 'Total' ? 'rgba(255,255,255,0.8)' : 'var(--text-muted)' }}>{label}</div>
                                  <div style={{ fontWeight: 700, fontSize: '0.9rem', color: label === 'Total' ? '#fff' : 'var(--text-primary)' }}>{fmtVal(val as any)}</div>
                                  <div style={{ fontSize: '0.65rem', color: label === 'Total' ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)' }}>kg</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {d.surface_treatment && (d.surface_treatment.blasting_standard || d.surface_treatment.paint_system) && (
                          <div style={{ background: 'var(--bg-secondary)', borderRadius: 10, padding: '0.875rem' }}>
                            <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.5rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Surface Treatment</div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.8125rem' }}>
                              {[['Blasting', d.surface_treatment.blasting_standard], ['Paint', d.surface_treatment.paint_system]].map(([l, v]) => v ? (
                                <div key={l}><div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{l}</div><div style={{ fontWeight: 600 }}>{v}</div></div>
                              ) : null)}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Structural Elements table */}
                    {d.structural_elements && d.structural_elements.length > 0 && (
                      <div style={{ marginBottom: '1rem' }}>
                        <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.5rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Structural Elements ({d.structural_elements.length})
                        </div>
                        <div style={{ overflowX: 'auto' }}>
                          <table className="data-table" style={{ fontSize: '0.8rem' }}>
                            <thead>
                              <tr>
                                <th>Tag</th><th>Description</th><th>Section</th><th>Grade</th>
                                <th className="text-center">Qty</th><th className="text-right">L (mm)</th>
                                <th className="text-right">W (mm)</th><th className="text-right">T (mm)</th>
                                <th className="text-right">Wt (kg)</th>
                              </tr>
                            </thead>
                            <tbody>
                              {d.structural_elements.map((el, i) => (
                                <tr key={i}>
                                  <td style={{ fontWeight: 700, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{el.support_tag || `#${i + 1}`}</td>
                                  <td style={{ minWidth: 140 }}>{el.item_description || '—'}</td>
                                  <td style={{ whiteSpace: 'nowrap' }}>{el.section_designation || el.section_type || '—'}</td>
                                  <td>{el.material_grade || '—'}</td>
                                  <td className="text-center">{fmtVal(el.quantity)}</td>
                                  <td className="text-right">{fmtVal(el.length_mm)}</td>
                                  <td className="text-right">{fmtVal(el.width_mm)}</td>
                                  <td className="text-right">{fmtVal(el.thickness_mm)}</td>
                                  <td className="text-right">{fmtVal(el.total_weight_kg)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Bolts & Plates */}
                    {d.bolts_and_plates && d.bolts_and_plates.length > 0 && (
                      <div style={{ marginBottom: '1rem' }}>
                        <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.5rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Bolts & Plates ({d.bolts_and_plates.length})
                        </div>
                        <div style={{ overflowX: 'auto' }}>
                          <table className="data-table" style={{ fontSize: '0.8rem' }}>
                            <thead><tr><th>Description</th><th>Size</th><th>Grade</th><th className="text-right">L (mm)</th><th className="text-center">Qty</th></tr></thead>
                            <tbody>
                              {d.bolts_and_plates.map((bp, i) => (
                                <tr key={i}>
                                  <td>{bp.item_description || '—'}</td>
                                  <td>{bp.size_designation || '—'}</td>
                                  <td>{bp.grade || '—'}</td>
                                  <td className="text-right">{fmtVal(bp.length_mm)}</td>
                                  <td className="text-center">{fmtVal(bp.quantity)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* General Notes */}
                    {d.drawing_metadata?.general_notes && d.drawing_metadata.general_notes.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.5rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>General Notes</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                          {d.drawing_metadata.general_notes.map((note, i) => (
                            <div key={i} style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem', background: 'var(--bg-secondary)', borderRadius: 6 }}>{note}</div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Ambiguities */}
                    {d.ambiguities && d.ambiguities.length > 0 && (
                      <div style={{ marginTop: '0.75rem' }}>
                        <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.5rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Ambiguities ({d.ambiguities.length})
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.5rem' }}>
                          {d.ambiguities.map((a, i) => (
                            <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '0.625rem', fontSize: '0.8rem' }}>
                              <div style={{ fontWeight: 700 }}>{a.location || `Issue ${i + 1}`}</div>
                              <div style={{ color: 'var(--text-secondary)', marginTop: 2 }}>{a.issue}</div>
                              <div style={{ color: 'var(--text-muted)', marginTop: 4, fontSize: '0.75rem' }}>Assumption: {a.assumption_made || '—'}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Flags */}
                    {d.flags && d.flags.length > 0 && (
                      <div className="alert alert-warning" style={{ marginTop: '0.75rem' }}>
                        <AlertTriangle size={14} />
                        <div style={{ fontSize: '0.8rem' }}>
                          <strong>Flags:</strong>
                          <ul style={{ margin: '4px 0 0 14px' }}>
                            {d.flags.map((f, i) => <li key={i}><strong>{f.field}:</strong> {f.reason}</li>)}
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {ext.error && (
                  <div className="card-body">
                    <div className="alert alert-warning"><AlertTriangle size={14} /><span>Extraction failed: {ext.error}</span></div>
                  </div>
                )}
              </div>
            )
          })}

          {/* Edit mode — editable flat items for costing */}
          {editMode && confirmedItems.length > 0 && (
            <div className="card animate-fade-in">
              <div className="card-header">
                <div className="card-title">Edit Costing Items</div>
                <span className="badge badge-neutral">{confirmedItems.length} items</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ fontSize: '0.8rem' }}>
                  <thead>
                    <tr>
                      <th>Tag</th><th>Description</th><th>Type</th>
                      <th className="text-center">Qty</th><th className="text-right">L (mm)</th>
                      <th className="text-right">W (mm)</th><th className="text-right">T (mm)</th>
                      <th>Grade</th>
                    </tr>
                  </thead>
                  <tbody>
                    {confirmedItems.map((item, i) => (
                      <tr key={i}>
                        {(['item_tag','description','section_type'] as const).map(key => (
                          <td key={key}>
                            <input
                              className="form-input"
                              style={{ fontSize: '0.75rem', padding: '0.25rem 0.4rem', minWidth: key === 'description' ? 140 : 70 }}
                              value={(item as any)[key] ?? ''}
                              onChange={e => setConfirmedItems(prev => prev.map((x, idx) => idx === i ? { ...x, [key]: e.target.value } : x))}
                            />
                          </td>
                        ))}
                        {(['quantity','length_mm','width_mm','thickness_mm','material_grade'] as const).map(key => (
                          <td key={key} className={key !== 'material_grade' ? 'text-right' : ''}>
                            <input
                              className="form-input"
                              style={{ fontSize: '0.75rem', padding: '0.25rem 0.4rem', minWidth: 60, textAlign: key !== 'material_grade' ? 'right' : 'left' }}
                              value={(item as any)[key] ?? ''}
                              onChange={e => setConfirmedItems(prev => prev.map((x, idx) => idx === i ? { ...x, [key]: e.target.value || null } : x))}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {confirmedItems.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <h3>No items extracted</h3>
              <p>The AI couldn't find structured data. Try re-extracting with additional context.</p>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.25rem' }}>
            <button className="btn btn-secondary" onClick={() => setStep('extract')}>Re-extract</button>
            <button className="btn btn-primary" onClick={handleConfirm} disabled={loading || !confirmedItems.length} style={{ minWidth: 180 }}>
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

