import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Download, FileSpreadsheet, AlertTriangle } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

export default function ExcelGenerator() {
  const { jobId: paramJobId } = useParams()
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<any[]>([])
  const [selectedJob, setSelectedJob] = useState(paramJobId || '')
  const [job, setJob] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    api.get('/estimate/jobs?limit=50').then(r => setJobs(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedJob) {
      api.get(`/estimate/jobs/${selectedJob}`).then(r => setJob(r.data)).catch(() => setJob(null))
    }
  }, [selectedJob])

  const download = async () => {
    if (!selectedJob) { toast.error('Select a job first'); return }
    setDownloading(true)
    try {
      const res = await api.post(`/estimate/generate-excel?job_id=${selectedJob}`, {}, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url
      a.download = `${job?.job_number || selectedJob}_costing_sheet.xlsx`; a.click()
      URL.revokeObjectURL(url)
      toast.success('Excel costing sheet downloaded!')
    } catch (e: any) { toast.error(e.message) }
    finally { setDownloading(false) }
  }

  const sheet = job?.costing_sheets?.[0]
  const totals = sheet?.totals || {}

  return (
    <div className="animate-fade-in" style={{ maxWidth: 860, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Excel Generator</h1>
          <p className="page-subtitle">Generate a formatted Excel costing sheet with preserved formulas</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="card">
            <div className="card-header"><div className="card-title">Select Job</div></div>
            <div className="card-body">
              <div className="form-group">
                <label className="form-label">Job <span className="required">*</span></label>
                <select className="form-select" value={selectedJob} onChange={e => setSelectedJob(e.target.value)}>
                  <option value="">Select a completed job…</option>
                  {jobs.filter(j => j.status === 'completed').map(j => (
                    <option key={j.id} value={j.id}>{j.job_number} — {j.client_name || 'No client'}</option>
                  ))}
                </select>
              </div>
              {job && (
                <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <InfoRow label="Job Number" value={job.job_number} />
                  <InfoRow label="Client" value={job.client_name || '—'} />
                  <InfoRow label="Project" value={job.project_name || '—'} />
                  <InfoRow label="Status" value={<span className={`badge ${job.status === 'completed' ? 'badge-success' : 'badge-warning'}`}>{job.status}</span>} />
                </div>
              )}
            </div>
          </div>

          <div className="alert alert-info">
            <FileSpreadsheet size={16} />
            <div style={{ fontSize: '0.8125rem' }}>
              The Excel file includes 4 sheets: <strong>Job Summary</strong>, <strong>Costing Sheet</strong> (with live formulas), <strong>Rates Config</strong>, and <strong>Audit Trail</strong>.
            </div>
          </div>

          <button className="btn btn-success btn-lg" onClick={download} disabled={!selectedJob || downloading || !sheet}>
            {downloading
              ? <><span className="spinner" style={{ width: 18, height: 18 }} /> Generating…</>
              : <><Download size={18} /> Download Excel Sheet</>}
          </button>

          {selectedJob && !sheet && (
            <div className="alert alert-warning">
              <AlertTriangle size={16} />
              <span>This job has no completed costing sheet. Run the costing engine first via New Estimate.</span>
            </div>
          )}
        </div>

        <div>
          {sheet ? (
            <div className="card">
              <div className="card-header"><div className="card-title">Cost Summary Preview</div></div>
              <div className="card-body">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {[
                    ['Total Weight', `${(totals.total_weight_kg || 0).toFixed(2)} kg`],
                    ['Material Cost', fmt(totals.total_material_cost)],
                    ['Fabrication Cost', fmt(totals.total_fabrication_cost)],
                    ['Welding Cost', fmt(totals.total_welding_cost)],
                    ['Consumables', fmt(totals.total_consumables_cost)],
                    ['Cutting', fmt(totals.total_cutting_cost)],
                    ['Surface Treatment', fmt(totals.total_surface_treatment_cost)],
                    ['Direct Cost', fmt(totals.total_direct_cost)],
                    [`Overhead (${totals.overhead_percentage}%)`, fmt(totals.overhead_cost)],
                    [`Profit (${totals.profit_margin_percentage}%)`, fmt(totals.profit_amount)],
                  ].map(([l, v]) => (
                    <div key={l} className="cost-row"><span className="cost-label">{l}</span><span className="cost-value">{v}</span></div>
                  ))}
                  <div className="cost-row total">
                    <span>SELLING PRICE</span>
                    <span>{fmt(totals.selling_price)}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card" style={{ height: '100%' }}>
              <div className="empty-state" style={{ paddingTop: '4rem' }}>
                <div className="empty-state-icon">📊</div>
                <h3>Select a completed job</h3>
                <p>Choose a job from the dropdown to preview costs and download the Excel sheet.</p>
                <button className="btn btn-primary btn-sm" onClick={() => navigate('/estimate/new')}>
                  Start New Estimate
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function fmt(v?: number) {
  if (v == null) return '—'
  return `AED ${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
}

function InfoRow({ label, value }: { label: string; value: any }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{value}</span>
    </div>
  )
}
