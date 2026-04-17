import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, AlertTriangle, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

type DrawingMetadata = {
  project_name?: string
  unit_area?: string
  drawing_number?: string
  revision?: string
  client?: string
  consultant?: string
  contractor?: string
  work_order_number?: string
  scale?: string
  date_issued?: string
  referenced_drawings?: string[]
  general_notes?: string[]
}

type StructuralElement = {
  support_tag?: string
  item_description?: string
  section_type?: string
  section_designation?: string
  material_grade?: string
  length_mm?: number | null
  width_mm?: number | null
  thickness_mm?: number | null
  quantity?: number | null
  unit_weight_kg_per_m?: number | null
  total_weight_kg?: number | null
  weld_type?: string
  weld_size_mm?: number | null
  weld_length_mm?: number | null
  surface_area_m2?: number | null
  notes?: string
}

type BoltPlateItem = {
  item_description?: string
  size_designation?: string
  grade?: string
  length_mm?: number | null
  quantity?: number | null
  notes?: string
}

type AmbiguityItem = {
  location?: string
  issue?: string
  assumption_made?: string
}

type SurfaceTreatment = {
  blasting_standard?: string
  paint_system?: string
  galvanizing_required?: boolean
  galvanized_members?: string[]
  total_surface_area_m2?: number | null
}

type WeightSummary = {
  total_structural_steel_kg?: number | null
  total_plates_kg?: number | null
  grand_total_steel_kg?: number | null
}

type DimensionItem = {
  item_tag?: string
  description?: string
  section_type?: string
  quantity?: number | null
  length_mm?: number | null
  width_mm?: number | null
  thickness_mm?: number | null
  od_mm?: number | null
  material_grade?: string | null
  confidence?: number
}

type FlagItem = {
  field?: string
  reason?: string
}

type ExtractionResult = {
  drawing_metadata?: DrawingMetadata | null
  structural_elements?: StructuralElement[]
  bolts_and_plates?: BoltPlateItem[]
  surface_treatment?: SurfaceTreatment | null
  weight_summary?: WeightSummary | null
  dimensions?: DimensionItem[]
  summary?: string
  overall_confidence?: number
  member_types?: string[]
  material_references?: string[]
  annotations?: string[]
  fabrication_notes?: string[]
  ambiguities?: AmbiguityItem[]
  flags?: FlagItem[]
}

export default function DrawingReader() {
  const [file, setFile] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [uploadCollapsed, setUploadCollapsed] = useState(false)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: useCallback((accepted: File[]) => {
      setFile(accepted[0] || null)
      setUploadCollapsed(false)
    }, []),
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/plain': ['.txt', '.csv'],
    },
  })

  const extract = async () => {
    if (!file) { toast.error('Please select a drawing file'); return }
    setLoading(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (context) fd.append('additional_context', context)
      const res = await api.post('/drawing/extract', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      const extractionResult = res.data
      setResult(extractionResult)
      setUploadCollapsed(true)
      const itemCount = extractionResult.structural_elements?.length || extractionResult.dimensions?.length || 0
      toast.success(`Extracted ${itemCount} items at ${Math.round((extractionResult.overall_confidence || 0) * 100)}% confidence`)
    } catch (e: any) {
      console.error(e)
      const msg = e.response?.data?.detail || e.message
      toast.error(`Error: ${msg}`, { duration: 6000 })
    } finally {
      setLoading(false)
    }
  }

  const confidence = (result?.overall_confidence || 0) * 100

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1100, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Drawing Reader</h1>
          <p className="page-subtitle">Upload a fabrication drawing or GA drawing to extract engineering data</p>
        </div>
      </div>

      {/* Upload panel — collapsible once results are loaded */}
      <div className="card" style={{ marginBottom: '1.25rem', transition: 'all 0.3s ease' }}>
        <div
          className="card-header"
          style={{ cursor: result ? 'pointer' : 'default', userSelect: 'none' }}
          onClick={() => result && setUploadCollapsed(c => !c)}
        >
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={16} />
            {file ? file.name : 'Upload Drawing'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {loading && <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Extracting…</span>}
            {result && !loading && (
              <span className={`badge ${confidence >= 70 ? 'badge-success' : 'badge-warning'}`}>
                {confidence.toFixed(0)}% confidence
              </span>
            )}
            {result && (uploadCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />)}
          </div>
        </div>

        {!uploadCollapsed && (
          <div className="card-body" style={{ paddingTop: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 260px', minWidth: 220 }}>
                <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragover' : ''}`} style={{ padding: '1.25rem 1rem' }}>
                  <input {...getInputProps()} />
                  <div className="upload-icon"><Upload size={20} /></div>
                  <div className="upload-title" style={{ fontSize: '0.875rem' }}>{file ? file.name : 'Drop drawing here or click to browse'}</div>
                  <div className="upload-subtitle">PDF, DOCX, Excel, TXT, or image (PNG / JPG)</div>
                </div>
              </div>
              <div style={{ flex: '1 1 260px', minWidth: 220, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Additional Context (optional)</label>
                  <textarea className="form-textarea" placeholder="e.g. Structural steel pipe rack, units mm, material A36…" value={context} onChange={e => setContext(e.target.value)} rows={3} />
                  <span className="form-help">Helps the AI understand context</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button className="btn btn-primary" onClick={extract} disabled={loading || !file} style={{ minWidth: 140 }}>
                    {loading
                      ? <><span className="spinner" style={{ width: 15, height: 15 }} /> Extracting…</>
                      : 'Extract Data'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '3rem', marginBottom: '1.25rem' }}>
          <div style={{ textAlign: 'center' }}>
            <div className="spinner spinner-lg" style={{ margin: '0 auto 1rem' }} />
            <div style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>AI is reading the drawing…</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: 4 }}>This may take 15–30 seconds for multi-page PDFs</div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && (
        <div className="card">
          <div className="empty-state" style={{ padding: '3rem 1rem' }}>
            <div className="empty-state-icon">📐</div>
            <h3>No drawing loaded</h3>
            <p>Upload a fabrication or GA drawing above to see extracted engineering data.</p>
          </div>
        </div>
      )}

      {/* Results — full-width, each card fades in */}
      {result && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

          {/* Summary bar */}
          <div className="card animate-fade-in">
            <div className="card-header">
              <div className="card-title">Extraction Summary</div>
              <span className={`badge ${confidence >= 70 ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
                {confidence.toFixed(0)}% CONFIDENCE
              </span>
            </div>
            <div className="card-body" style={{ paddingTop: '0.5rem' }}>
              {result.summary && <p style={{ fontSize: '0.875rem', margin: 0 }}>{result.summary}</p>}
              {result.member_types && result.member_types.length > 0 && (
                <div style={{ marginTop: '0.6rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {result.member_types.map((t, i) => <span key={i} className="badge badge-primary">{t}</span>)}
                </div>
              )}
            </div>
          </div>

          {/* Two-column info row: metadata + surface/weight */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '1rem' }}>

            {result.drawing_metadata && hasMetadata(result.drawing_metadata) && (
              <div className="card animate-fade-in">
                <div className="card-header"><div className="card-title">Drawing Metadata</div></div>
                <div className="card-body">
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem 1.5rem', fontSize: '0.875rem' }}>
                    {renderMetadataRow('Project', result.drawing_metadata.project_name)}
                    {renderMetadataRow('Unit / Area', result.drawing_metadata.unit_area)}
                    {renderMetadataRow('Drawing No.', result.drawing_metadata.drawing_number)}
                    {renderMetadataRow('Revision', result.drawing_metadata.revision)}
                    {renderMetadataRow('Client', result.drawing_metadata.client)}
                    {renderMetadataRow('Consultant', result.drawing_metadata.consultant)}
                    {renderMetadataRow('Contractor', result.drawing_metadata.contractor)}
                    {renderMetadataRow('Work Order', result.drawing_metadata.work_order_number)}
                    {renderMetadataRow('Scale', result.drawing_metadata.scale)}
                    {renderMetadataRow('Date Issued', result.drawing_metadata.date_issued)}
                  </div>
                  {renderStringList('Referenced Drawings', result.drawing_metadata.referenced_drawings)}
                  {renderStringList('General Notes', result.drawing_metadata.general_notes)}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {result.surface_treatment && hasSurfaceTreatment(result.surface_treatment) && (
                <div className="card animate-fade-in">
                  <div className="card-header"><div className="card-title">Surface Treatment</div></div>
                  <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem 1.5rem', fontSize: '0.875rem' }}>
                      {renderMetadataRow('Blasting', result.surface_treatment.blasting_standard)}
                      {renderMetadataRow('Paint System', result.surface_treatment.paint_system)}
                      {renderMetadataRow('Galvanizing', result.surface_treatment.galvanizing_required != null ? (result.surface_treatment.galvanizing_required ? 'Yes' : 'No') : undefined)}
                      {renderMetadataRow('Area (m²)', formatValue(result.surface_treatment.total_surface_area_m2))}
                    </div>
                    {renderStringList('Galvanized Members', result.surface_treatment.galvanized_members)}
                  </div>
                </div>
              )}

              {result.weight_summary && hasWeightSummary(result.weight_summary) && (
                <div className="card animate-fade-in">
                  <div className="card-header"><div className="card-title">Weight Summary</div></div>
                  <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', fontSize: '0.875rem' }}>
                      <div style={{ textAlign: 'center', padding: '0.75rem', background: 'var(--bg-secondary)', borderRadius: 8 }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>Structural Steel</div>
                        <div style={{ fontWeight: 700, fontSize: '1rem' }}>{formatValue(result.weight_summary.total_structural_steel_kg)}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>kg</div>
                      </div>
                      <div style={{ textAlign: 'center', padding: '0.75rem', background: 'var(--bg-secondary)', borderRadius: 8 }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>Plates</div>
                        <div style={{ fontWeight: 700, fontSize: '1rem' }}>{formatValue(result.weight_summary.total_plates_kg)}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>kg</div>
                      </div>
                      <div style={{ textAlign: 'center', padding: '0.75rem', background: 'var(--accent-primary)', borderRadius: 8 }}>
                        <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.8)', marginBottom: 4 }}>Grand Total</div>
                        <div style={{ fontWeight: 700, fontSize: '1rem', color: '#fff' }}>{formatValue(result.weight_summary.grand_total_steel_kg)}</div>
                        <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.8)' }}>kg</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Structural Elements — full width */}
          {result.structural_elements && result.structural_elements.length > 0 && (
            <div className="card animate-fade-in">
              <div className="card-header">
                <div className="card-title">Structural Elements</div>
                <span className="badge badge-neutral">{result.structural_elements.length} items</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ fontSize: '0.8125rem' }}>
                  <thead>
                    <tr>
                      <th style={{ whiteSpace: 'nowrap' }}>Tag</th>
                      <th>Description</th>
                      <th style={{ whiteSpace: 'nowrap' }}>Section</th>
                      <th style={{ whiteSpace: 'nowrap' }}>Grade</th>
                      <th className="text-center">Qty</th>
                      <th className="text-right" style={{ whiteSpace: 'nowrap' }}>L (mm)</th>
                      <th className="text-right" style={{ whiteSpace: 'nowrap' }}>W (mm)</th>
                      <th className="text-right" style={{ whiteSpace: 'nowrap' }}>T (mm)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>Weld</th>
                      <th className="text-right" style={{ whiteSpace: 'nowrap' }}>Wt (kg)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.structural_elements.map((el, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 700, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{el.support_tag || `#${i + 1}`}</td>
                        <td style={{ minWidth: 160 }}>{el.item_description || '—'}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{el.section_designation || el.section_type || '—'}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{el.material_grade || '—'}</td>
                        <td className="text-center">{formatValue(el.quantity)}</td>
                        <td className="text-right">{formatValue(el.length_mm)}</td>
                        <td className="text-right">{formatValue(el.width_mm)}</td>
                        <td className="text-right">{formatValue(el.thickness_mm)}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{formatWeld(el)}</td>
                        <td className="text-right">{formatValue(el.total_weight_kg)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Bolts and Plates — full width */}
          {result.bolts_and_plates && result.bolts_and_plates.length > 0 && (
            <div className="card animate-fade-in">
              <div className="card-header">
                <div className="card-title">Bolts and Plates</div>
                <span className="badge badge-neutral">{result.bolts_and_plates.length} items</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ fontSize: '0.8125rem' }}>
                  <thead>
                    <tr>
                      <th>Description</th>
                      <th style={{ whiteSpace: 'nowrap' }}>Size</th>
                      <th style={{ whiteSpace: 'nowrap' }}>Grade</th>
                      <th className="text-right" style={{ whiteSpace: 'nowrap' }}>L (mm)</th>
                      <th className="text-center">Qty</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.bolts_and_plates.map((item, i) => (
                      <tr key={i}>
                        <td>{item.item_description || '—'}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{item.size_designation || '—'}</td>
                        <td>{item.grade || '—'}</td>
                        <td className="text-right">{formatValue(item.length_mm)}</td>
                        <td className="text-center">{formatValue(item.quantity)}</td>
                        <td>{item.notes || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Dimensions (legacy) — only show if no structural_elements */}
          {(!result.structural_elements || result.structural_elements.length === 0) && result.dimensions && result.dimensions.length > 0 && (
            <div className="card animate-fade-in">
              <div className="card-header">
                <div className="card-title">Extracted Dimensions</div>
                <span className="badge badge-neutral">{result.dimensions.length} items</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ fontSize: '0.8125rem' }}>
                  <thead>
                    <tr>
                      <th>Tag</th><th>Description</th><th>Type</th>
                      <th className="text-center">Qty</th>
                      <th className="text-right">L (mm)</th><th className="text-right">W (mm)</th>
                      <th className="text-right">T (mm)</th><th className="text-right">OD (mm)</th>
                      <th>Conf.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.dimensions.map((d, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 700, fontFamily: 'monospace' }}>{d.item_tag || `#${i + 1}`}</td>
                        <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.description}</td>
                        <td><span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>{d.section_type}</span></td>
                        <td className="text-center">{d.quantity}</td>
                        <td className="text-right">{d.length_mm ?? '—'}</td>
                        <td className="text-right">{d.width_mm ?? '—'}</td>
                        <td className="text-right">{d.thickness_mm ?? '—'}</td>
                        <td className="text-right">{d.od_mm ?? '—'}</td>
                        <td>
                          <div className="confidence-bar" style={{ width: 48 }}>
                            <div className={`confidence-fill ${(d.confidence || 0) >= 0.8 ? 'conf-high' : (d.confidence || 0) >= 0.5 ? 'conf-medium' : 'conf-low'}`} style={{ width: `${(d.confidence || 0) * 100}%` }} />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Notes row */}
          {((result.material_references?.length ?? 0) > 0 || (result.annotations?.length ?? 0) > 0 || (result.fabrication_notes?.length ?? 0) > 0) && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              {result.material_references && result.material_references.length > 0 && (
                <div className="card animate-fade-in">
                  <div className="card-header"><div className="card-title">Material References</div></div>
                  <div className="card-body" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {result.material_references.map((item, i) => <span key={i} className="badge badge-neutral">{item}</span>)}
                  </div>
                </div>
              )}
              {result.annotations && result.annotations.length > 0 && (
                <div className="card animate-fade-in">
                  <div className="card-header"><div className="card-title">Annotations</div></div>
                  <div className="card-body" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {result.annotations.map((item, i) => <span key={i} className="badge badge-neutral">{item}</span>)}
                  </div>
                </div>
              )}
              {result.fabrication_notes && result.fabrication_notes.length > 0 && (
                <div className="card animate-fade-in">
                  <div className="card-header"><div className="card-title">Fabrication Notes</div></div>
                  <div className="card-body" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {result.fabrication_notes.map((item, i) => <span key={i} className="badge badge-neutral">{item}</span>)}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Ambiguities */}
          {result.ambiguities && result.ambiguities.length > 0 && (
            <div className="card animate-fade-in">
              <div className="card-header">
                <div className="card-title">Ambiguities</div>
                <span className="badge badge-warning">{result.ambiguities.length}</span>
              </div>
              <div className="card-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '0.75rem' }}>
                {result.ambiguities.map((item, i) => (
                  <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '0.75rem' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.8125rem' }}>{item.location || `Issue #${i + 1}`}</div>
                    <div style={{ fontSize: '0.8125rem', marginTop: 4 }}>{item.issue || '—'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 6 }}>Assumption: {item.assumption_made || '—'}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Flags */}
          {result.flags && result.flags.length > 0 && (
            <div className="alert alert-warning animate-fade-in">
              <AlertTriangle size={16} />
              <div>
                <strong>Flags ({result.flags.length}):</strong>
                <ul style={{ margin: '4px 0 0 16px', fontSize: '0.8125rem' }}>
                  {result.flags.map((f, i) => <li key={i}><strong>{f.field}:</strong> {f.reason}</li>)}
                </ul>
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  )
}

function renderMetadataRow(label: string, value?: string) {
  return (
    <div key={label}>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ fontWeight: 600 }}>{value || '—'}</div>
    </div>
  )
}

function renderStringList(title: string, items?: string[]) {
  if (!items || items.length === 0) return null
  return (
    <div style={{ marginTop: '0.875rem' }}>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 6 }}>{title}</div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {items.map((item, index) => (
          <span key={`${title}-${index}`} className="badge badge-neutral">{item}</span>
        ))}
      </div>
    </div>
  )
}

function formatValue(value?: number | string | null) {
  if (value == null || value === '') return '—'
  return value
}

function formatWeld(element: StructuralElement) {
  if (!element.weld_type && !element.weld_size_mm && !element.weld_length_mm) return '—'
  return [element.weld_type, element.weld_size_mm ? `${element.weld_size_mm} mm` : null, element.weld_length_mm ? `${element.weld_length_mm} mm` : null]
    .filter(Boolean)
    .join(' / ')
}

function hasMetadata(metadata: DrawingMetadata) {
  return Object.values(metadata).some(value => Array.isArray(value) ? value.length > 0 : Boolean(value))
}

function hasSurfaceTreatment(surfaceTreatment: SurfaceTreatment) {
  return Boolean(
    surfaceTreatment.blasting_standard ||
    surfaceTreatment.paint_system ||
    surfaceTreatment.galvanizing_required ||
    (surfaceTreatment.galvanized_members && surfaceTreatment.galvanized_members.length > 0) ||
    surfaceTreatment.total_surface_area_m2
  )
}

function hasWeightSummary(weightSummary: WeightSummary) {
  return Boolean(
    weightSummary.total_structural_steel_kg ||
    weightSummary.total_plates_kg ||
    weightSummary.grand_total_steel_kg
  )
}
