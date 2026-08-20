import { useState, useCallback, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useDropzone } from 'react-dropzone'
import { File as FileIcon, FileSpreadsheet, FileText, Image as ImageIcon, Plus, RefreshCw, Send, Upload, X } from 'lucide-react'
import { api, ApiError } from '../api/client'
import toast from 'react-hot-toast'

type AttachmentKind = 'pdf' | 'image' | 'document'

interface Attachment {
  file: File
  kind: AttachmentKind
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  model?: string
  attachments?: string[]
  isError?: boolean
}

const ACCEPT = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/gif': ['.gif'],
  'image/webp': ['.webp'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'application/json': ['.json'],
  'text/html': ['.html'],
  'application/xml': ['.xml'],
  'text/csv': ['.csv'],
  'text/tab-separated-values': ['.tsv'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/rtf': ['.rtf'],
  'application/vnd.oasis.opendocument.text': ['.odt'],
  'application/vnd.ms-powerpoint': ['.ppt'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
}

const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp'])

const MAX_ATTACHMENTS = 10

const DEFAULT_PROMPT = `Analyze all drawings, BOMs, notes and client emails. Return material quantities for the complete project.

Rules:

- Calculate every structural steel component separately and combine them into one \`"Structural Steel Material"\` row.
- Include plates, pipes, tubes, beams, channels, angles, bars, sections, caps, brackets and other fabricated steel parts.
- Multiply unit quantities by the total project quantity before summing.
- List all non-structural and purchased items separately using their exact drawing descriptions and specifications.
- Combine only identical items.
- Avoid omissions and double-counting.
- Omit any item whose quantity is \`0\`, \`null\` or cannot be determined.
- Never output placeholder or example rows.
- Do not include costs, labour, formulas, calculations or lengthy remarks.
- Include a 2-3 sentence \`summary\` field: what the document(s) are, how the structural steel total was derived, and any assumptions, ambiguities or gaps found.

Steel calculation priority:

1. BOM weight
2. Specified kg/m × length
3. Calculate from dimensions using 7850 kg/m³
4. Reasonable engineering assumption if only minor information is missing

Formulas:

- Plate: L × W × T × 7850
- Round bar: πD²/4 × L × 7850
- Pipe: π/4 × (OD² − ID²) × L × 7850
- Section: kg/m × length

Return only valid JSON. Round weights to two decimals and counts to whole numbers.

{
"summary": "2-3 sentence conclusion: what the document(s) are, how the steel total was derived, and any assumptions/ambiguities.",
"items": [
{
"description": "Structural Steel Material",
"quantity": 1250.50,
"unit": "kg",
"remarks": "Total project quantity, and specfiy how much quantity for 1 project "
},
{
"name": "Exact item name",
"quantity": 20,
"unit": "nos",
"remarks": null
}
]
}`

function kindOf(file: File): AttachmentKind {
  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  if (ext === 'pdf') return 'pdf'
  if (IMAGE_EXTENSIONS.has(ext)) return 'image'
  return 'document'
}

interface ExtractedItem {
  description?: string | null
  name?: string | null
  quantity: number | null
  unit?: string | null
  remarks?: string | null
}

interface ExtractionResult {
  items: ExtractedItem[]
  summary?: string | null
}

function itemLabel(item: ExtractedItem) {
  return item.description || item.name || '—'
}

function parseExtraction(content: string): ExtractionResult | null {
  const candidates = [content.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim()]
  const braceMatch = content.match(/\{[\s\S]*\}/)
  if (braceMatch) candidates.push(braceMatch[0])

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate)
      if (parsed && Array.isArray(parsed.items)) return parsed as ExtractionResult
    } catch {
      // not JSON — try the next candidate
    }
  }
  return null
}

interface CustomerInfo {
  customerName: string
  refNo: string
  enquiryNo: string
  jobNo: string
  attention: string
  contact: string
}

const EMPTY_CUSTOMER: CustomerInfo = {
  customerName: '', refNo: '', enquiryNo: '', jobNo: '', attention: '', contact: '',
}

type ReviewTab = 'items' | 'customer' | 'summary'

function defaultRateFor(label: string): string {
  const low = label.toLowerCase()
  if (low.includes('handrail')) return '4.50'
  if (low.includes('grating')) return '7.50'
  if (low.includes('paint')) return '52.00'
  return ''
}

function ExtractionReview({ extraction, model }: { extraction: ExtractionResult; model?: string }) {
  // Seeded once from the LLM output, then edited locally — the raw chat message never changes.
  const [items, setItems] = useState<ExtractedItem[]>(() => extraction.items)
  const [activeTab, setActiveTab] = useState<ReviewTab>('items')
  const [customer, setCustomer] = useState<CustomerInfo>(EMPTY_CUSTOMER)
  const [rates, setRates] = useState<Record<number, string>>({})
  const [showConfirm, setShowConfirm] = useState(false)
  const [exporting, setExporting] = useState(false)

  const steelIndex = items.findIndex((i) => itemLabel(i).toLowerCase().includes('structural steel'))
  const steelItem = steelIndex >= 0 ? items[steelIndex] : undefined

  const updateItem = (idx: number, patch: Partial<ExtractedItem>) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  }

  const openConfirm = () => {
    setRates((prev) => {
      const next = { ...prev }
      items.forEach((item, idx) => {
        if (idx === steelIndex) return
        if (next[idx] === undefined) next[idx] = defaultRateFor(itemLabel(item))
      })
      return next
    })
    setShowConfirm(true)
  }

  const handleGenerateExcel = async () => {
    setExporting(true)
    try {
      const payload = {
        items: items.map((item, idx) => ({
          description: item.description,
          name: item.name,
          quantity: item.quantity,
          unit: item.unit,
          remarks: item.remarks,
          rate: idx === steelIndex || !rates[idx] ? null : Number(rates[idx]),
        })),
        customer,
      }
      const res = await api.post('/chat/export-excel', payload, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `JobCosting_${customer.jobNo || new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      setShowConfirm(false)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Failed to generate the costing sheet.'
      toast.error(msg)
    } finally {
      setExporting(false)
    }
  }

  const tabs: { id: ReviewTab; label: string; count?: number }[] = [
    { id: 'items', label: 'Items', count: items.length },
    { id: 'customer', label: 'Customer Information' },
    { id: 'summary', label: 'Summary' },
  ]

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Drawing Review</div>
          <div className="card-subtitle">
            {items.length} item{items.length === 1 ? '' : 's'}
            {steelItem?.quantity != null && ` · ${steelItem.quantity.toLocaleString()} kg steel`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {model && <span className="badge badge-neutral">{model}</span>}
          <button className="btn btn-success btn-sm" onClick={openConfirm}>
            <FileSpreadsheet size={13} /> Generate Excel
          </button>
        </div>
      </div>

      <div className="card-body">
        <div className="tabs" style={{ marginBottom: '1rem' }}>
          {tabs.map((t) => (
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

        {activeTab === 'items' && (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Description</th>
                  <th>Quantity</th>
                  <th>Unit</th>
                  <th>Remarks</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => (
                  <tr key={idx}>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{idx + 1}</td>
                    <td>
                      <input
                        className="cell-input"
                        defaultValue={itemLabel(item)}
                        onBlur={(e) => updateItem(idx, { description: e.target.value, name: undefined })}
                      />
                    </td>
                    <td>
                      <input
                        className="cell-input"
                        type="number"
                        defaultValue={item.quantity ?? ''}
                        placeholder="—"
                        onBlur={(e) => updateItem(idx, { quantity: e.target.value ? Number(e.target.value) : null })}
                        style={{ textAlign: 'right' }}
                      />
                    </td>
                    <td>
                      <input
                        className="cell-input"
                        defaultValue={item.unit ?? ''}
                        placeholder="—"
                        onBlur={(e) => updateItem(idx, { unit: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className="cell-input"
                        defaultValue={item.remarks ?? ''}
                        placeholder="—"
                        onBlur={(e) => updateItem(idx, { remarks: e.target.value })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'customer' && (
          <div className="card" style={{ maxWidth: 500, boxShadow: 'none' }}>
            <div className="card-header"><h3 className="card-title">Customer Information</h3></div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
              {Object.entries(customer).map(([k, v]) => (
                <div key={k} className="form-group">
                  <label className="form-label">{k.replace(/([A-Z])/g, ' $1').trim()}</label>
                  <input
                    className="form-input"
                    value={v}
                    onChange={(e) => setCustomer((prev) => ({ ...prev, [k]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'summary' && (
          <div className="card" style={{ boxShadow: 'none' }}>
            <div className="card-header"><h3 className="card-title">Extraction Summary</h3></div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {extraction.summary || (
                  <>
                    Extracted {items.length} item{items.length === 1 ? '' : 's'} from the attached drawings/BOMs
                    {steelItem?.quantity != null && `, totalling ${steelItem.quantity.toLocaleString()} kg of structural steel`}.
                  </>
                )}
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.5rem' }}>
                {[
                  { label: 'Items', value: String(items.length) },
                  { label: 'Structural Steel', value: steelItem?.quantity != null ? `${steelItem.quantity.toLocaleString()} kg` : '—' },
                  { label: 'Non-Structural Items', value: String(items.length - (steelIndex >= 0 ? 1 : 0)) },
                  { label: 'Model', value: model || '—' },
                ].map(({ label, value }) => (
                  <div key={label} style={{ padding: '0.75rem', background: 'var(--gray-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '0.2rem', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{label}</p>
                    <p style={{ fontSize: '1rem', fontWeight: 700 }}>{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {showConfirm && createPortal(
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.55)', backdropFilter: 'blur(2px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: '1rem',
          }}
          onClick={() => !exporting && setShowConfirm(false)}
        >
          <div
            className="card"
            style={{ maxWidth: 640, width: '100%', maxHeight: '90vh', overflowY: 'auto', boxShadow: 'var(--shadow-xl)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-header">
              <div>
                <h3 className="card-title">Confirm before generating</h3>
                <p className="card-subtitle">Review customer details and pricing — structural steel uses the sheet's standard rate.</p>
              </div>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div>
                <p style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: '0.6rem' }}>Customer Information</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
                  {Object.entries(customer).map(([k, v]) => (
                    <div key={k} className="form-group">
                      <label className="form-label">
                        {k.replace(/([A-Z])/g, ' $1').trim()}{k === 'customerName' && ' *'}
                      </label>
                      <input
                        className="form-input"
                        value={v}
                        onChange={(e) => setCustomer((prev) => ({ ...prev, [k]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: '0.6rem' }}>Pricing (per unit)</p>
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Qty</th>
                        <th>Unit</th>
                        <th>Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => idx === steelIndex ? (
                        <tr key={idx}>
                          <td>{itemLabel(item)}</td>
                          <td className="text-right">{item.quantity != null ? item.quantity.toLocaleString() : '—'}</td>
                          <td style={{ color: 'var(--text-muted)' }}>{item.unit || '—'}</td>
                          <td style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Standard rate</td>
                        </tr>
                      ) : (
                        <tr key={idx}>
                          <td>{itemLabel(item)}</td>
                          <td className="text-right">{item.quantity != null ? item.quantity.toLocaleString() : '—'}</td>
                          <td style={{ color: 'var(--text-muted)' }}>{item.unit || '—'}</td>
                          <td>
                            <input
                              type="number"
                              className="form-input"
                              style={{ width: 100 }}
                              placeholder="0.00"
                              value={rates[idx] ?? ''}
                              onChange={(e) => setRates((prev) => ({ ...prev, [idx]: e.target.value }))}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.625rem' }}>
                <button className="btn btn-ghost" onClick={() => setShowConfirm(false)} disabled={exporting}>
                  Cancel
                </button>
                <button
                  className="btn btn-success"
                  onClick={handleGenerateExcel}
                  disabled={exporting || !customer.customerName.trim()}
                >
                  <FileSpreadsheet size={14} /> {exporting ? 'Generating…' : 'Confirm & Generate'}
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const prompt = DEFAULT_PROMPT
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID())
  const [lastResponseId, setLastResponseId] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const onDrop = useCallback((accepted: File[]) => {
    if (!accepted.length) return
    setAttachments((prev) => {
      const next: Attachment[] = accepted.map((file) => ({ file, kind: kindOf(file) }))
      const merged = [...prev, ...next].slice(0, MAX_ATTACHMENTS)
      if (prev.length + next.length > MAX_ATTACHMENTS) {
        toast.error(`Only the first ${MAX_ATTACHMENTS} files were kept`)
      }
      return merged
    })
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPT,
  })

  const removeAttachment = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx))
  }

  const newChat = () => {
    setMessages([])
    setAttachments([])
    setLastResponseId(null)
    setSessionId(crypto.randomUUID())
  }

  const send = async () => {
    const text = prompt.trim()
    if (!text || loading || attachments.length === 0) return
    const pending = attachments
    setMessages((prev) => [...prev, {
      role: 'user',
      content: text,
      attachments: pending.map((a) => a.file.name),
    }])
    setAttachments([])
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('prompt', text)
      fd.append('session_id', sessionId)
      if (lastResponseId) fd.append('previous_response_id', lastResponseId)
      pending.forEach((a) => fd.append('files', a.file))
      const res = await api.post('/chat/inference', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      console.log('[LLM Extraction] LLM response:', res.data.response)
      console.log('[LLM Extraction] Model:', res.data.model)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.response, model: res.data.model }])
      setLastResponseId(res.data.response_id || null)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Something went wrong. Please try again.'
      toast.error(msg)
      setMessages((prev) => [...prev, { role: 'assistant', content: msg, isError: true }])
    } finally {
      setLoading(false)
    }
  }

  const attachmentIcon = (kind: AttachmentKind) => {
    if (kind === 'pdf') return <FileText size={12} />
    if (kind === 'image') return <ImageIcon size={12} />
    return <FileIcon size={12} />
  }

  return (
    <div className="animate-fade-in" style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">LLM Extraction</h1>
          <p className="page-subtitle">Attach drawings, BOMs, notes or client emails to extract a full quantity takeoff</p>
        </div>
        <button className="btn btn-secondary" onClick={newChat} disabled={loading}>
          <Plus size={15} /> New Extraction
        </button>
      </div>

      {/* Upload — hidden once a result is showing; "New Extraction" brings it back */}
      {messages.length === 0 && !loading && (
        <>
          <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragover' : ''}`}>
            <input {...getInputProps()} />
            <div className="upload-icon"><Upload size={22} /></div>
            <p className="upload-title">Drop drawing files here or click to browse</p>
            <p className="upload-subtitle">PDF, image, or document — up to {MAX_ATTACHMENTS} files, 50 MB total</p>
          </div>

          {attachments.length > 0 && (
            <div className="file-list">
              {attachments.map((a, i) => (
                <div key={i} className="file-item">
                  <div className="file-icon other">{attachmentIcon(a.kind)}</div>
                  <div className="file-info">
                    <div className="file-name">{a.file.name}</div>
                    <div className="file-size">{(a.file.size / 1024 / 1024).toFixed(1)} MB</div>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={() => removeAttachment(i)}>
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <p className="form-help" style={{ marginTop: '0.75rem' }}>
            The quantity takeoff prompt is applied automatically to every analysis. Follow-up sends continue the same conversation.
          </p>

          <button
            className="btn btn-primary btn-lg"
            style={{ width: '100%', marginTop: '0.75rem' }}
            onClick={send}
            disabled={attachments.length === 0 || loading}
          >
            <Send size={16} /> Analyse
          </button>
        </>
      )}

      {/* Results */}
      <div style={{ marginTop: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {messages.length === 0 && !loading && (
          <div className="empty-state">
            <div className="empty-state-icon">📄</div>
            <h3>No results yet</h3>
            <p>Attach the project drawings, BOMs, notes, or client emails above and analyse.</p>
          </div>
        )}
        {messages.map((m, i) => {
          if (m.role === 'user') return null

          const extraction = !m.isError ? parseExtraction(m.content) : null
          if (extraction) {
            return <ExtractionReview key={i} extraction={extraction} model={m.model} />
          }

          return (
            <div key={i} className={`alert ${m.isError ? 'alert-error' : 'alert-info'}`} style={{ whiteSpace: 'pre-wrap' }}>
              <div>
                {m.content}
                {m.model && !m.isError && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>{m.model}</div>
                )}
              </div>
            </div>
          )
        })}
        {loading && (
          <div className="alert alert-info" style={{ alignItems: 'center' }}>
            <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />
            <span>Analysing…</span>
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
