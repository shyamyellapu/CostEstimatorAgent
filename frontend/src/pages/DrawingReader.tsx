import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, AlertTriangle, CheckCircle } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

export default function DrawingReader() {
  const [file, setFile] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: useCallback((accepted: File[]) => setFile(accepted[0] || null), []),
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg'],
    },
  })

  const extract = async () => {
    if (!file) { toast.error('Please select a drawing file'); return }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (context) fd.append('additional_context', context)
      const res = await api.post('/drawing/extract', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      
      const extractionResult = res.data
      setResult(extractionResult)
      
      if (extractionResult.summary?.toLowerCase().includes('failed')) {
        toast.error('AI extraction had issues. See summary.')
      } else {
        toast.success(`Extracted ${extractionResult.dimensions?.length || 0} items`)
      }
    } catch (e: any) {
      console.error(e)
      const msg = e.response?.data?.detail || e.message
      toast.error(`Error: ${msg}`, { duration: 6000 })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-in" style={{ maxWidth: 860, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Drawing Reader</h1>
          <p className="page-subtitle">Upload a fabrication drawing or GA drawing to extract engineering data</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="card">
            <div className="card-header"><div className="card-title">Upload Drawing</div></div>
            <div className="card-body">
              <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragover' : ''}`}>
                <input {...getInputProps()} />
                <div className="upload-icon"><Upload size={22} /></div>
                <div className="upload-title">{file ? file.name : 'Drop drawing here'}</div>
                <div className="upload-subtitle">PDF or image (PNG / JPG)</div>
              </div>
              <div className="form-group mt-4">
                <label className="form-label">Additional Context (optional)</label>
                <textarea className="form-textarea" placeholder="e.g. This is a structural steel pipe rack, units are mm, material is A36…" value={context} onChange={e => setContext(e.target.value)} rows={3} />
                <span className="form-help">Help the AI understand the drawing context better</span>
              </div>
            </div>
            <div className="card-footer" style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" onClick={extract} disabled={loading || !file}>
                {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Extracting…</> : 'Extract Data'}
              </button>
            </div>
          </div>

          <div className="alert alert-info">
            <AlertTriangle size={16} />
            <div style={{ fontSize: '0.8rem' }}>
              <strong>Vision AI:</strong> Drawings (PDF and Images) are now processed using Llama 3.2 Vision. For best results, ensure drawings are clear and high-resolution.
            </div>
          </div>
        </div>

        {/* Results */}
        <div>
          {!result && !loading && (
            <div className="card" style={{ height: '100%' }}>
              <div className="empty-state" style={{ paddingTop: '4rem' }}>
                <div className="empty-state-icon">📐</div>
                <h3>No drawing loaded</h3>
                <p>Upload a drawing to see extracted engineering data here.</p>
              </div>
            </div>
          )}
          {loading && (
            <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
              <div style={{ textAlign: 'center' }}>
                <div className="spinner spinner-lg" style={{ margin: '0 auto 1rem' }} />
                <div style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>AI is reading the drawing…</div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: 4 }}>This may take 10–30 seconds</div>
              </div>
            </div>
          )}
          {result && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">Extraction Summary</div>
                  <span className={`badge ${result.overall_confidence >= 0.7 ? 'badge-success' : 'badge-warning'}`}>
                    {(result.overall_confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
                <div className="card-body">
                  <p style={{ fontSize: '0.875rem' }}>{result.summary}</p>
                  {result.member_types?.length > 0 && (
                    <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {result.member_types.map((t: string, i: number) => (
                        <span key={i} className="badge badge-primary">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {result.dimensions?.length > 0 && (
                <div className="card">
                  <div className="card-header"><div className="card-title">Extracted Dimensions ({result.dimensions.length})</div></div>
                  <div style={{ overflowX: 'auto' }}>
                    <table className="data-table">
                      <thead><tr><th>Tag</th><th>Description</th><th>Type</th><th>Qty</th><th>L (mm)</th><th>W (mm)</th><th>T (mm)</th><th>OD (mm)</th><th>Conf.</th></tr></thead>
                      <tbody>
                        {result.dimensions.map((d: any, i: number) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 700, fontSize: '0.8rem' }}>{d.item_tag || `#${i+1}`}</td>
                            <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.description}</td>
                            <td><span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>{d.section_type}</span></td>
                            <td className="text-center">{d.quantity}</td>
                            <td className="text-right">{d.length_mm ?? '—'}</td>
                            <td className="text-right">{d.width_mm ?? '—'}</td>
                            <td className="text-right">{d.thickness_mm ?? '—'}</td>
                            <td className="text-right">{d.od_mm ?? '—'}</td>
                            <td>
                              <div className="confidence-bar" style={{ width: 50 }}>
                                <div className={`confidence-fill ${d.confidence >= 0.8 ? 'conf-high' : d.confidence >= 0.5 ? 'conf-medium' : 'conf-low'}`} style={{ width: `${d.confidence * 100}%` }} />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {result.flags?.length > 0 && (
                <div className="alert alert-warning">
                  <AlertTriangle size={16} />
                  <div>
                    <strong>Flags ({result.flags.length}):</strong>
                    <ul style={{ margin: '4px 0 0 16px', fontSize: '0.8125rem' }}>
                      {result.flags.map((f: any, i: number) => <li key={i}><strong>{f.field}:</strong> {f.reason}</li>)}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
