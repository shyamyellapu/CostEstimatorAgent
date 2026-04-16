import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, AlertTriangle, Download } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

export default function BOQParser() {
  const [file, setFile] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: useCallback((accepted: File[]) => setFile(accepted[0] || null), []),
    multiple: false,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/plain': ['.txt', '.csv'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
  })

  const parse = async () => {
    if (!file) { toast.error('Please select a BOQ file'); return }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (context) fd.append('additional_context', context)
      const res = await api.post('/boq/parse', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setResult(res.data)
      toast.success(`Parsed ${res.data.dimensions?.length || 0} line items`)
    } catch (e: any) { toast.error(e.message) }
    finally { setLoading(false) }
  }

  const exportCSV = () => {
    if (!result?.dimensions?.length) return
    const headers = ['Item Tag', 'Description', 'Section Type', 'Qty', 'Length (mm)', 'Width (mm)', 'Thickness (mm)', 'OD (mm)', 'Material', 'Confidence']
    const rows = result.dimensions.map((d: any) => [
      d.item_tag || '', d.description || '', d.section_type || '',
      d.quantity || '', d.length_mm || '', d.width_mm || '', d.thickness_mm || '',
      d.od_mm || '', d.material_grade || '', d.confidence || ''
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'boq_parsed.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="animate-fade-in" style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">BOQ Parser</h1>
          <p className="page-subtitle">Upload a Bill of Quantities to extract structured line items</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="card">
            <div className="card-header"><div className="card-title">Upload BOQ</div></div>
            <div className="card-body">
              <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragover' : ''}`}>
                <input {...getInputProps()} />
                <div className="upload-icon"><Upload size={22} /></div>
                <div className="upload-title">{file ? file.name : 'Drop BOQ here'}</div>
                <div className="upload-subtitle">PDF, Excel, CSV, DOCX, TXT</div>
              </div>
              <div className="form-group mt-4">
                <label className="form-label">Additional Context</label>
                <textarea className="form-textarea" rows={3} placeholder="e.g. Units are in mm, this is for a structural steel project…" value={context} onChange={e => setContext(e.target.value)} />
              </div>
            </div>
            <div className="card-footer" style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" onClick={parse} disabled={loading || !file}>
                {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Parsing…</> : 'Parse BOQ'}
              </button>
            </div>
          </div>

          {result && (
            <div className="card">
              <div className="card-header"><div className="card-title">Parse Summary</div></div>
              <div className="card-body">
                <p style={{ fontSize: '0.875rem' }}>{result.summary}</p>
                <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {result.member_types?.map((t: string, i: number) => (
                    <span key={i} className="badge badge-primary">{t}</span>
                  ))}
                </div>
                <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  <span>Items: <strong style={{ color: 'var(--text-primary)' }}>{result.dimensions?.length || 0}</strong></span>
                  <span>Confidence: <strong style={{ color: result.overall_confidence >= 0.7 ? 'var(--success-600)' : 'var(--warning-600)' }}>{(result.overall_confidence * 100).toFixed(0)}%</strong></span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div>
          {!result ? (
            <div className="card" style={{ height: '100%' }}>
              <div className="empty-state" style={{ paddingTop: '4rem' }}>
                <div className="empty-state-icon">📋</div>
                <h3>No BOQ loaded</h3>
                <p>Upload a Bill of Quantities to extract and review line items.</p>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button className="btn btn-secondary btn-sm" onClick={exportCSV}>
                  <Download size={14} /> Export CSV
                </button>
              </div>
              <div className="card">
                <div className="card-header"><div className="card-title">Line Items ({result.dimensions?.length || 0})</div></div>
                <div className="table-container" style={{ border: 'none' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Tag</th><th>Description</th><th>Type</th><th>Qty</th>
                        <th className="text-right">L (mm)</th><th className="text-right">T (mm)</th>
                        <th>Conf.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.dimensions?.map((d: any, i: number) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 700, fontSize: '0.8rem' }}>{d.item_tag || `#${i+1}`}</td>
                          <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.8rem' }}>{d.description}</td>
                          <td><span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>{d.section_type}</span></td>
                          <td className="text-center">{d.quantity}</td>
                          <td className="text-right">{d.length_mm ?? '—'}</td>
                          <td className="text-right">{d.thickness_mm ?? '—'}</td>
                          <td>
                            {d.confidence < 0.5 && <span title="Low confidence"><AlertTriangle size={12} color="var(--warning-500)" /></span>}
                            {d.confidence >= 0.5 && <span style={{ color: d.confidence >= 0.8 ? 'var(--success-600)' : 'var(--warning-600)', fontSize: '0.75rem', fontWeight: 600 }}>
                              {(d.confidence * 100).toFixed(0)}%
                            </span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
