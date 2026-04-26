import { useCallback, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { api } from '../api/client'
import {
  AlertTriangle, CheckCircle, ChevronDown, ChevronUp,
  FileText, FileSpreadsheet, RefreshCw, Upload,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ProjectInfo {
  drawing_no: string
  revision: string
  title: string
  client: string
  contractor: string
  package_description: string
}

interface MemberRow {
  section: string
  role: string
  length_m: number
  kg_per_m: number
  pieces: number
  weight_kg: number
  is_estimated: boolean
}

interface Plate {
  description: string
  thickness_mm: number
  total_area_m2: number
  pieces: number
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
  subtotal_no_consum: number
  overhead: number
  consumables: number
  grand_total: number
  selling_price: number
  net_profit: number
  profit_pct: number
  markup_pct: number
  member_rows: MemberRow[]
  plates: Plate[]
}

interface CustomerFields {
  customerName: string
  refNo: string
  enquiryNo: string
  jobNo: string
  attention: string
  contact: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function aed(n: number) {
  return `AED ${n.toLocaleString('en-AE', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function recompute(costing: Costing, markupPct: number): Costing {
  const mk = markupPct / 100
  const selling = (costing.subtotal_no_consum + costing.overhead) * (1 + mk)
  const consumables = selling / 20
  const grandTotal = costing.subtotal_no_consum + consumables + costing.overhead
  const netProfit = selling - grandTotal
  return {
    ...costing,
    selling_price: Math.round(selling),
    consumables: Math.round(consumables * 100) / 100,
    grand_total: Math.round(grandTotal * 100) / 100,
    net_profit: Math.round(netProfit * 100) / 100,
    profit_pct: selling ? Math.round((netProfit / selling) * 10000) / 100 : 0,
    markup_pct: markupPct,
  }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
type Stage = 'upload' | 'review'

export default function DrawingCosting() {
  const [stage, setStage] = useState<Stage>('upload')
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [downloadSuccess, setDownloadSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [warning, setWarning] = useState<string | null>(null)

  // extraction
  const [project, setProject] = useState<ProjectInfo | null>(null)
  const [notes, setNotes] = useState<string>('')
  const [rawExtraction, setRawExtraction] = useState<object | null>(null)

  // costing (mutable via markup slider)
  const [costing, setCosting] = useState<Costing | null>(null)
  const [markupPct, setMarkupPct] = useState(34)

  // customer fields
  const [customer, setCustomer] = useState<CustomerFields>({
    customerName: '', refNo: '', enquiryNo: '', jobNo: '',
    attention: '', contact: '',
  })

  const fileRef = useRef<File | null>(null)

  // ---- Upload & analyse ----
  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0]
    if (!file) return
    fileRef.current = file
    setError(null)
    setWarning(null)
    setLoading(true)

    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('markup_pct', String(markupPct))
      const { data } = await api.post('/drawing-costing/analyse', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180_000,
      })

      const proj: ProjectInfo = data.extraction?.project || {}
      setProject(proj)
      setNotes(data.extraction?.notes || '')
      setRawExtraction(data.extraction)

      if (data.warning) setWarning(data.warning)

      if (data.costing) {
        const computed = recompute(data.costing, markupPct)
        setCosting(computed)
        setCustomer(prev => ({
          ...prev,
          customerName: prev.customerName || proj.contractor || '',
          jobNo:        prev.jobNo        || proj.drawing_no  || '',
        }))
        setStage('review')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }, [markupPct])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: loading,
  })

  // ---- Markup slider handler ----
  const handleMarkup = (val: number) => {
    setMarkupPct(val)
    if (costing) setCosting(recompute(costing, val))
  }

  // ---- Export as Excel ----
  const handleExport = async () => {
    if (!costing || !rawExtraction) return
    setExporting(true)
    setDownloadSuccess(false)
    setError(null)
    try {
      const resp = await api.post(
        '/drawing-costing/generate-excel',
        { extraction: rawExtraction, customer, markup_pct: markupPct },
        { responseType: 'blob', timeout: 60_000 },
      )
      const url   = URL.createObjectURL(new Blob([resp.data as BlobPart]))
      const a     = document.createElement('a')
      const jobNo = customer.jobNo || 'XXXX'
      a.href      = url
      a.download  = `JobCosting_${jobNo}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      setDownloadSuccess(true)
      setTimeout(() => setDownloadSuccess(false), 4000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate Excel')
    } finally {
      setExporting(false)
    }
  }

  // ---- Reset ----
  const reset = () => {
    setStage('upload')
    setProject(null)
    setCosting(null)
    setRawExtraction(null)
    setNotes('')
    setWarning(null)
    setError(null)
    setDownloadSuccess(false)
    setMarkupPct(34)
    setCustomer({ customerName: '', refNo: '', enquiryNo: '', jobNo: '', attention: '', contact: '' })
    fileRef.current = null
  }

  // ================================================================
  // Render
  // ================================================================
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Drawing Costing</h1>
        {stage === 'review' && costing && (
          <button
            onClick={handleExport}
            disabled={exporting}
            style={{
              ...styles.btnPrimary,
              background: downloadSuccess ? '#16a34a' : 'var(--accent)',
              minWidth: 190,
            }}
          >
            {exporting
              ? <><RefreshCw size={15} style={{ animation: 'spin 1s linear infinite' }} /> Exporting…</>
              : downloadSuccess
              ? <><CheckCircle size={15} /> Downloaded!</>
              : <><FileSpreadsheet size={15} /> Export as Excel</>}
          </button>
        )}
      </div>
      <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
        Upload a structural steel drawing PDF to generate a Job Costing Sheet
      </p>

      {/* ---- Error / Warning banners ---- */}
      {error && (
        <div style={styles.banner('error')}>
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}
      {warning && (
        <div style={styles.banner('warning')}>
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <span>{warning} No members detected — please verify the drawing or enter data manually.</span>
        </div>
      )}

      {/* ================================================================ */}
      {/* STAGE: upload                                                     */}
      {/* ================================================================ */}
      {stage === 'upload' && (
        <div
          {...getRootProps()}
          style={{
            ...styles.dropzone,
            borderColor: isDragActive ? 'var(--accent)' : 'var(--border)',
            background:  isDragActive ? 'var(--accent-subtle, #f0f4ff)' : 'var(--surface)',
          }}
        >
          <input {...getInputProps()} />
          {loading ? (
            <div style={styles.dropzoneInner}>
              <RefreshCw size={36} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent)' }} />
              <p style={{ marginTop: 12, color: 'var(--text-muted)' }}>
                Analysing drawing with Claude AI…
              </p>
            </div>
          ) : (
            <div style={styles.dropzoneInner}>
              <Upload size={36} style={{ color: 'var(--accent)' }} />
              <p style={{ marginTop: 12, fontWeight: 600 }}>
                {isDragActive ? 'Drop the PDF here' : 'Drag & drop a drawing PDF'}
              </p>
              <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                or <span style={{ color: 'var(--accent)', textDecoration: 'underline', cursor: 'pointer' }}>browse</span>
                {' '}— max 32 MB
              </p>
            </div>
          )}
        </div>
      )}

      {/* ================================================================ */}
      {/* STAGE: review                                                     */}
      {/* ================================================================ */}
      {stage === 'review' && costing && project && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* 8.1 Project information */}
          <Section title="Project Information (from drawing)">
            <InfoGrid items={[
              ['Drawing No.',       project.drawing_no],
              ['Revision',          project.revision],
              ['Title',             project.title],
              ['Client',            project.client],
              ['Contractor',        project.contractor],
              ['Package',           project.package_description],
              ['Source PDF',        fileRef.current?.name ?? ''],
            ]} />
          </Section>

          {/* 8.2 Customer & Reference */}
          <Section title="Customer & Reference">
            <div style={styles.fieldGrid}>
              {(
                [
                  ['customerName', 'Customer Name'],
                  ['refNo',        'Ref No'],
                  ['enquiryNo',    'Enquiry No'],
                  ['jobNo',        'Job No'],
                  ['attention',    'Attention'],
                  ['contact',      'Contact No'],
                ] as [keyof CustomerFields, string][]
              ).map(([key, label]) => (
                <label key={key} style={styles.fieldLabel}>
                  <span style={styles.fieldLabelText}>{label}</span>
                  <input
                    style={styles.input}
                    value={customer[key]}
                    onChange={e => setCustomer(prev => ({ ...prev, [key]: e.target.value }))}
                    placeholder={label}
                  />
                </label>
              ))}
            </div>
          </Section>

          {/* 8.3 Material Takeoff */}
          <Section title="Material Takeoff">
            <div style={{ overflowX: 'auto' }}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {['Section','Role','Length (m)','kg/m','Pieces','Weight (kg)'].map(h => (
                      <th key={h} style={styles.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {costing.member_rows.map((r, i) => (
                    <tr key={i} style={{ background: r.is_estimated ? '#fffbeb' : undefined }}>
                      <td style={styles.td}>
                        {r.section}
                        {r.is_estimated && (
                          <span title="Weight estimated (section not in lookup table)"
                            style={{ marginLeft: 6, color: '#d97706', fontSize: 12 }}>⚠</span>
                        )}
                      </td>
                      <td style={styles.td}>{r.role}</td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>{r.length_m.toFixed(2)}</td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>{r.kg_per_m}</td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>{r.pieces}</td>
                      <td style={{ ...styles.td, textAlign: 'right', fontWeight: 600 }}>{r.weight_kg.toFixed(1)}</td>
                    </tr>
                  ))}
                  {costing.plates.length > 0 && (
                    <tr style={{ background: '#f8f8f8' }}>
                      <td style={styles.td} colSpan={2}>
                        Plates ({costing.plates.map(p => p.description).join(', ')})
                      </td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>—</td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>—</td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>
                        {costing.plates.reduce((s, p) => s + p.pieces, 0)}
                      </td>
                      <td style={{ ...styles.td, textAlign: 'right', fontWeight: 600 }}>
                        {costing.plates
                          .reduce((s, p) => s + p.thickness_mm * p.total_area_m2 * 7.85, 0)
                          .toFixed(1)}
                      </td>
                    </tr>
                  )}
                </tbody>
                <tfoot>
                  <tr style={{ background: 'var(--surface-alt, #f0f4ff)' }}>
                    <td style={{ ...styles.td, fontWeight: 700 }} colSpan={5}>Total Steel Weight</td>
                    <td style={{ ...styles.td, textAlign: 'right', fontWeight: 700 }}>
                      {costing.total_steel_kg.toFixed(1)} kg
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Section>

          {/* 8.4 Derived Quantities */}
          <Section title="Derived Quantities">
            <div style={styles.kpiGrid}>
              <KPI label="Bolts (M20×90)"           value={`${costing.bolts} Nos`} />
              <KPI label="Paint Material"            value={`${costing.paint_litres} litres`} />
              <KPI label="Surface Area (blast/paint)" value={`${costing.surface_area_sqm} SQM`} />
              <KPI label="Welding Manhours"          value={`${costing.welding_mh} MH`} />
              <KPI label="Fabrication Manhours"      value={`${costing.fabrication_mh} MH`} />
              <KPI label="MPI/DPT Visits"            value={`${costing.mpi_visits} Visits`} />
            </div>
          </Section>

          {/* 8.5 Cost Summary + Markup slider */}
          <Section title="Cost Summary">
            {/* Markup slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
              <span style={{ fontWeight: 600, minWidth: 70 }}>Markup %</span>
              <input
                type="range" min={0} max={80} step={1}
                value={markupPct}
                onChange={e => handleMarkup(Number(e.target.value))}
                style={{ flex: 1, accentColor: 'var(--accent)' }}
              />
              <span style={{
                minWidth: 52, textAlign: 'center', fontWeight: 700,
                background: 'var(--accent)', color: '#fff',
                borderRadius: 6, padding: '2px 10px',
              }}>
                {markupPct}%
              </span>
            </div>

            {/* Line items */}
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Line Item</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>Amount (AED)</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Steel Material',        costing.steel_mat_cost],
                  ['Bolts',                 costing.bolt_cost],
                  ['Paint Material',        costing.paint_mat_cost],
                  ['Welding Labour',        costing.weld_cost],
                  ['Fabrication Labour',    costing.fab_cost],
                  ['Blasting',              costing.blast_cost],
                  ['Painting Application',  costing.paint_app_cost],
                  ['MPI/DPT',              costing.mpi_cost],
                  ['QA/QC Docs',           costing.qaqc_cost],
                  ['Packing',              costing.packing_cost],
                  ['Consumables (=SP/20)', costing.consumables],
                  ['Overhead (S54)',       costing.overhead],
                ].map(([label, val]) => (
                  <tr key={String(label)}>
                    <td style={styles.td}>{String(label)}</td>
                    <td style={{ ...styles.td, textAlign: 'right' }}>{aed(Number(val))}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ background: 'var(--surface-alt, #f0f4ff)', fontWeight: 700 }}>
                  <td style={styles.td}>Grand Total Cost</td>
                  <td style={{ ...styles.td, textAlign: 'right' }}>{aed(costing.grand_total)}</td>
                </tr>
                <tr style={{ background: '#dbeafe', fontWeight: 700 }}>
                  <td style={styles.td}>Selling Price</td>
                  <td style={{ ...styles.td, textAlign: 'right', color: '#1d4ed8' }}>{aed(costing.selling_price)}</td>
                </tr>
                <tr style={{ background: '#dcfce7', fontWeight: 700 }}>
                  <td style={styles.td}>Net Profit ({costing.profit_pct.toFixed(1)}%)</td>
                  <td style={{ ...styles.td, textAlign: 'right', color: '#15803d' }}>{aed(costing.net_profit)}</td>
                </tr>
              </tfoot>
            </table>
          </Section>

          {/* 8.6 Takeoff notes */}
          {notes && (
            <div style={styles.banner('info')}>
              <FileText size={16} style={{ flexShrink: 0 }} />
              <span><strong>Takeoff notes:</strong> {notes}</span>
            </div>
          )}

          {/* 8.7 Actions */}
          <div style={{ display: 'flex', gap: 12, justifyContent: 'space-between', alignItems: 'center', paddingTop: 8 }}>
            <button onClick={reset} style={styles.btnSecondary} disabled={exporting}>
              <RefreshCw size={16} /> Start Over
            </button>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {downloadSuccess && (
                <span style={{ color: '#16a34a', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <CheckCircle size={15} /> JobCosting_{customer.jobNo || 'XXXX'}.xlsx downloaded
                </span>
              )}
              <button
                onClick={handleExport}
                disabled={exporting}
                style={{
                  ...styles.btnPrimary,
                  background: downloadSuccess ? '#16a34a' : 'var(--accent)',
                  minWidth: 200,
                }}
              >
                {exporting
                  ? <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} /> Exporting…</>
                  : downloadSuccess
                  ? <><CheckCircle size={16} /> Export Again</>
                  : <><FileSpreadsheet size={16} /> Export as Excel</>}
              </button>
            </div>
          </div>
        </div>
      )}


    </div>
  )
}

// ---------------------------------------------------------------------------
// Small reusable sub-components
// ---------------------------------------------------------------------------
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 10,
      overflow: 'hidden', background: 'var(--surface)',
    }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', background: 'var(--surface-alt, #f8fafc)',
          border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 14,
          color: 'var(--text-primary)',
        }}
      >
        {title}
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && <div style={{ padding: '16px' }}>{children}</div>}
    </div>
  )
}

function InfoGrid({ items }: { items: [string, string][] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
      {items.filter(([, v]) => v).map(([label, value]) => (
        <div key={label}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
          <div style={{ fontWeight: 600, fontSize: 14, marginTop: 2 }}>{value}</div>
        </div>
      ))}
    </div>
  )
}

function KPI({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px',
      background: 'var(--surface)',
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>{value}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Style objects
// ---------------------------------------------------------------------------
const styles = {
  dropzone: {
    border: '2px dashed',
    borderRadius: 12,
    padding: '56px 24px',
    textAlign: 'center' as const,
    cursor: 'pointer',
    transition: 'border-color 0.2s, background 0.2s',
  },
  dropzoneInner: { display: 'flex', flexDirection: 'column' as const, alignItems: 'center' },
  banner: (type: 'error' | 'warning' | 'info') => ({
    display: 'flex', alignItems: 'flex-start', gap: 10,
    padding: '12px 14px', borderRadius: 8, marginBottom: 16,
    fontSize: 14,
    ...(type === 'error'   ? { background: '#fee2e2', color: '#991b1b' } :
        type === 'warning' ? { background: '#fef9c3', color: '#854d0e' } :
                             { background: '#dbeafe', color: '#1e40af' }),
  }),
  fieldGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: 16,
  },
  fieldLabel: { display: 'flex', flexDirection: 'column' as const, gap: 4 },
  fieldLabelText: { fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' as const, letterSpacing: '0.05em' },
  input: {
    border: '1px solid var(--border)', borderRadius: 6,
    padding: '7px 10px', fontSize: 14, width: '100%', boxSizing: 'border-box' as const,
    background: 'var(--surface)', color: 'var(--text-primary)',
  },
  table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 13 },
  th: {
    background: 'var(--surface-alt, #f8fafc)',
    padding: '8px 10px', textAlign: 'left' as const,
    fontWeight: 700, fontSize: 12, textTransform: 'uppercase' as const,
    letterSpacing: '0.04em', borderBottom: '1px solid var(--border)',
  },
  td: { padding: '8px 10px', borderBottom: '1px solid var(--border)' },
  kpiGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 },
  btnPrimary: {
    display: 'inline-flex', alignItems: 'center', gap: 8,
    background: 'var(--accent)', color: '#fff',
    border: 'none', borderRadius: 8, padding: '10px 20px',
    fontWeight: 600, fontSize: 14, cursor: 'pointer',
  },
  btnSecondary: {
    display: 'inline-flex', alignItems: 'center', gap: 8,
    background: 'var(--surface)', color: 'var(--text-secondary)',
    border: '1px solid var(--border)', borderRadius: 8, padding: '10px 20px',
    fontWeight: 600, fontSize: 14, cursor: 'pointer',
  },
}
