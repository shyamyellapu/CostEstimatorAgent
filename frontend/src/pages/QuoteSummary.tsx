import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { ArrowLeft, Download } from 'lucide-react'

const COLORS = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316']

export default function QuoteSummary() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<any[]>([])
  const [selectedJobId, setSelectedJobId] = useState(jobId || '')
  const [job, setJob] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/estimate/jobs?limit=50').then(r => setJobs(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedJobId) {
      setLoading(true)
      api.get(`/estimate/jobs/${selectedJobId}`)
        .then(r => setJob(r.data))
        .catch(() => setJob(null))
        .finally(() => setLoading(false))
    }
  }, [selectedJobId])

  const sheet = job?.costing_sheets?.[0]
  const totals = sheet?.totals || {}

  const costData = sheet ? [
    { name: 'Material', value: totals.total_material_cost || 0 },
    { name: 'Fabrication', value: totals.total_fabrication_cost || 0 },
    { name: 'Welding', value: totals.total_welding_cost || 0 },
    { name: 'Consumables', value: totals.total_consumables_cost || 0 },
    { name: 'Cutting', value: totals.total_cutting_cost || 0 },
    { name: 'Surface', value: totals.total_surface_treatment_cost || 0 },
    { name: 'Overhead', value: totals.overhead_cost || 0 },
  ].filter(d => d.value > 0) : []

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1000, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Quote Summary</h1>
          <p className="page-subtitle">Full cost breakdown and visual analysis</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <select className="form-select" style={{ width: 280 }} value={selectedJobId} onChange={e => setSelectedJobId(e.target.value)}>
            <option value="">Select a job…</option>
            {jobs.map(j => <option key={j.id} value={j.id}>{j.job_number} — {j.client_name || 'No client'}</option>)}
          </select>
        </div>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: '3rem' }}><div className="spinner spinner-lg" style={{ margin: '0 auto' }} /></div>}

      {!selectedJobId && !loading && (
        <div className="empty-state">
          <div className="empty-state-icon">📈</div>
          <h3>Select a job</h3>
          <p>Choose a job from the dropdown above to view its cost summary and breakdown charts.</p>
        </div>
      )}

      {job && sheet && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Header info */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Job Number', value: job.job_number },
              { label: 'Client', value: job.client_name || '—' },
              { label: 'Total Weight', value: `${(totals.total_weight_kg || 0).toFixed(2)} kg` },
              { label: 'Selling Price', value: `AED ${(totals.selling_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}` },
            ].map(c => (
              <div key={c.label} className="card" style={{ textAlign: 'center' }}>
                <div className="card-body">
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{c.label}</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, marginTop: 4, color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>{c.value}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Pie chart */}
            <div className="card">
              <div className="card-header"><div className="card-title">Cost Distribution</div></div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie data={costData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                      {costData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => [`AED ${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, '']}
                      contentStyle={{ borderRadius: 8, border: '1px solid var(--border)', fontSize: 13 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Cost breakdown table */}
            <div className="card">
              <div className="card-header"><div className="card-title">Cost Breakdown</div></div>
              <div className="card-body">
                {[
                  ['Material Cost', totals.total_material_cost],
                  ['Fabrication Cost', totals.total_fabrication_cost],
                  ['Welding Cost', totals.total_welding_cost],
                  ['Consumables', totals.total_consumables_cost],
                  ['Cutting / Machining', totals.total_cutting_cost],
                  ['Surface Treatment', totals.total_surface_treatment_cost],
                ].map(([l, v]) => (
                  <div key={l} className="cost-row">
                    <span className="cost-label">{l as string}</span>
                    <span className="cost-value">AED {(v as number || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                ))}
                <div className="cost-row" style={{ marginTop: 6 }}>
                  <span className="cost-label font-semibold">Direct Cost</span>
                  <span className="cost-value">AED {(totals.total_direct_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="cost-row">
                  <span className="cost-label">Overhead ({totals.overhead_percentage}%)</span>
                  <span className="cost-value">AED {(totals.overhead_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="cost-row">
                  <span className="cost-label">Profit ({totals.profit_margin_percentage}%)</span>
                  <span className="cost-value">AED {(totals.profit_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="cost-row total">
                  <span>SELLING PRICE</span>
                  <span>AED {(totals.selling_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
            <button className="btn btn-secondary" onClick={() => navigate('/excel-generator')}>
              <Download size={16} /> Download Excel
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/cover-letter')}>
              Generate Cover Letter →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
