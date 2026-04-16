import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, AlertTriangle, Download, CheckCircle } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

export default function CoverLetterGenerator() {
  const [file, setFile] = useState<File | null>(null)
  const [jobId, setJobId] = useState('')
  const [loading, setLoading] = useState(false)
  const [parsed, setParsed] = useState<any>(null)
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null)
  const [pdfName, setPdfName] = useState('')

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: useCallback((accepted: File[]) => { setFile(accepted[0] || null); setParsed(null); setPdfBlob(null) }, []),
    multiple: false,
    accept: { 'application/pdf': ['.pdf'] },
  })

  const parseOnly = async () => {
    if (!file) { toast.error('Please upload a quotation PDF first'); return }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('quotation_file', file)
      const res = await api.post('/cover-letter/parse-quotation', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setParsed(res.data.parsed_data)
      toast.success('Quotation parsed successfully')
    } catch (e: any) { toast.error(e.message) }
    finally { setLoading(false) }
  }

  const generate = async () => {
    if (!file) { toast.error('Quotation upload is required to generate a cover letter'); return }
    if (!jobId.trim()) { toast.error('Please enter a Job ID'); return }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('quotation_file', file)
      fd.append('job_id', jobId)
      const res = await api.post('/cover-letter/generate', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
      })
      setPdfBlob(res.data)
      setPdfName(`${jobId}_cover_letter.pdf`)
      toast.success('Cover letter generated!')
    } catch (e: any) { toast.error(e.message) }
    finally { setLoading(false) }
  }

  const downloadPdf = () => {
    if (!pdfBlob) return
    const url = URL.createObjectURL(pdfBlob)
    const a = document.createElement('a'); a.href = url; a.download = pdfName; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="animate-fade-in" style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Cover Letter Generator</h1>
          <p className="page-subtitle">Generate a professional fabrication covering letter from an uploaded quotation</p>
        </div>
      </div>

      <div className="alert alert-warning" style={{ marginBottom: '1.5rem' }}>
        <AlertTriangle size={16} />
        <div>
          <strong>Quotation upload required.</strong> A covering letter cannot be generated without first uploading the client's quotation/RFQ document.
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left: Inputs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="card">
            <div className="card-header"><div className="card-title">Upload Quotation <span style={{ color: 'var(--error-500)' }}>*</span></div></div>
            <div className="card-body">
              <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragover' : ''}`}>
                <input {...getInputProps()} />
                <div className="upload-icon"><Upload size={22} /></div>
                {file
                  ? <><div className="upload-title" style={{ color: 'var(--success-600)' }}><CheckCircle size={16} style={{ display: 'inline', marginRight: 6 }} />{file.name}</div><div className="upload-subtitle">Quotation ready</div></>
                  : <><div className="upload-title">Drop quotation PDF here</div><div className="upload-subtitle">Only PDF supported</div></>
                }
              </div>
              <div className="form-group mt-4">
                <label className="form-label">Job ID <span className="required">*</span></label>
                <input className="form-input" placeholder="Enter Job ID from estimate…" value={jobId} onChange={e => setJobId(e.target.value)} />
                <span className="form-help">The Job ID links the cover letter to the costed job</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button className="btn btn-secondary" onClick={parseOnly} disabled={loading || !file} style={{ flex: 1 }}>
              {loading ? <span className="spinner" style={{ width: 16, height: 16 }} /> : <FileText size={16} />}
              Preview Parsed Data
            </button>
            <button className="btn btn-primary" onClick={generate} disabled={loading || !file || !jobId} style={{ flex: 1 }}>
              {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Generating…</> : 'Generate PDF →'}
            </button>
          </div>

          {pdfBlob && (
            <button className="btn btn-success btn-lg" onClick={downloadPdf}>
              <Download size={18} /> Download Cover Letter PDF
            </button>
          )}

          <div className="card" style={{ background: 'var(--gray-50)' }}>
            <div className="card-body">
              <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>What's included</div>
              <ul style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', paddingLeft: '1rem', lineHeight: 1.8 }}>
                <li>Professional introduction</li>
                <li>Fabrication-only scope clarification</li>
                <li>Exclusions and contractual protections</li>
                <li>AFC / drawings responsibility clause</li>
                <li>Quantity / weight commercial assumptions</li>
                <li>Delivery, risk transfer, and payment terms</li>
                <li>Validity and contractual basis</li>
                <li>Company branding, header, and signatory</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Right: Parsed preview */}
        <div>
          {!parsed && !pdfBlob ? (
            <div className="card" style={{ height: '100%' }}>
              <div className="empty-state" style={{ paddingTop: '4rem' }}>
                <div className="empty-state-icon">📄</div>
                <h3>Upload a quotation to begin</h3>
                <p>The AI will extract client, scope, exclusions, payment terms and other commercial details from the quotation PDF.</p>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {parsed && (
                <div className="card">
                  <div className="card-header"><div className="card-title">Extracted Quotation Data</div></div>
                  <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {[
                      ['Client', parsed.client],
                      ['Reference', parsed.reference_number],
                      ['Project', parsed.project],
                      ['Date', parsed.date],
                      ['Currency', parsed.currency],
                      ['Validity', parsed.validity],
                      ['Payment Terms', parsed.payment_terms],
                      ['Delivery Terms', parsed.delivery_terms],
                    ].map(([l, v]) => v && (
                      <div key={l} style={{ display: 'flex', gap: '0.5rem', fontSize: '0.8125rem' }}>
                        <span style={{ color: 'var(--text-muted)', minWidth: 120 }}>{l}:</span>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{v}</span>
                      </div>
                    ))}
                    {parsed.scope && (
                      <div style={{ marginTop: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Scope</div>
                        <p style={{ fontSize: '0.8125rem' }}>{parsed.scope}</p>
                      </div>
                    )}
                    {parsed.exclusions?.length > 0 && (
                      <div style={{ marginTop: '0.5rem' }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Exclusions</div>
                        <ul style={{ paddingLeft: '1rem', fontSize: '0.8125rem', lineHeight: 1.6 }}>
                          {parsed.exclusions.map((e: string, i: number) => <li key={i}>{e}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {pdfBlob && (
                <div className="alert alert-success">
                  <CheckCircle size={16} />
                  <span>Cover letter generated! Click <strong>Download</strong> to save the PDF.</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
