import { useEffect, useState } from 'react'
import { Save, RefreshCw, Database, CheckCircle } from 'lucide-react'
import { api } from '../api/client'
import toast from 'react-hot-toast'

interface Rate {
  key: string; name: string; category: string
  value: number; unit: string; description: string
}

const categoryColors: Record<string, string> = {
  Material:    '#3b82f6',
  Fabrication: '#8b5cf6',
  Welding:     '#f59e0b',
  Consumables: '#10b981',
  Cutting:     '#ef4444',
  Surface:     '#06b6d4',
  Overhead:    '#f97316',
  Profit:      '#22c55e',
}

export default function Settings() {
  const [rates, setRates] = useState<Rate[]>([])
  const [defaults, setDefaults] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [seeding, setSeeding] = useState(false)
  const [tab, setTab] = useState('rates')

  useEffect(() => {
    api.get('/settings').then(r => {
      setDefaults(r.data.rates || {})
      setRates(r.data.rate_details || [])
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const updateRate = (key: string, val: string) => {
    setRates(prev => prev.map(r => r.key === key ? { ...r, value: parseFloat(val) || 0 } : r))
    setDefaults(prev => ({ ...prev, [key]: parseFloat(val) || 0 }))
  }

  const save = async () => {
    setSaving(true)
    try {
      const updates = rates.map(r => ({ key: r.key, value: r.value }))
      await api.put('/settings', updates)
      toast.success('Rates saved successfully')
    } catch (e: any) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  const seedDefaults = async () => {
    setSeeding(true)
    try {
      await api.post('/settings/seed-defaults')
      toast.success('Default rates seeded')
      const r = await api.get('/settings')
      setRates(r.data.rate_details || [])
    } catch (e: any) { toast.error(e.message) }
    finally { setSeeding(false) }
  }

  const categories = [...new Set(rates.map(r => r.category))]

  return (
    <div className="animate-fade-in" style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Configure rates, AI provider, and company information</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-secondary" onClick={seedDefaults} disabled={seeding}>
            <Database size={16} /> {seeding ? 'Seeding…' : 'Seed Defaults'}
          </button>
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            <Save size={16} /> {saving ? 'Saving…' : 'Save Rates'}
          </button>
        </div>
      </div>

      <div className="tabs">
        {['rates', 'ai', 'company'].map(t => (
          <button key={t} className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'rates' ? '⚙️ Rate Library' : t === 'ai' ? '🤖 AI Provider' : '🏢 Company Info'}
          </button>
        ))}
      </div>

      {tab === 'rates' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem' }}><div className="spinner spinner-lg" style={{ margin: '0 auto' }} /></div>
          ) : rates.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <div className="empty-state-icon">⚙️</div>
                <h3>No rates configured</h3>
                <p>Click "Seed Defaults" to populate the rate library with standard values.</p>
                <button className="btn btn-primary" onClick={seedDefaults} disabled={seeding}>
                  <Database size={16} /> Seed Default Rates
                </button>
              </div>
            </div>
          ) : (
            categories.map(cat => {
              const catRates = rates.filter(r => r.category === cat)
              const color = categoryColors[cat] || '#6b7280'
              return (
                <div key={cat} className="card">
                  <div className="card-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                      <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
                      <div className="card-title">{cat}</div>
                    </div>
                  </div>
                  <div className="card-body">
                    <div className="grid grid-cols-2 gap-3">
                      {catRates.map(r => (
                        <div key={r.key} className="form-group">
                          <label className="form-label" style={{ fontSize: '0.75rem' }}>
                            {r.name}
                            <span style={{ color: 'var(--text-muted)', fontWeight: 400, marginLeft: 4 }}>({r.unit})</span>
                          </label>
                          <input
                            type="number"
                            className="form-input"
                            value={r.value}
                            step="0.01"
                            min="0"
                            onChange={e => updateRate(r.key, e.target.value)}
                          />
                          {r.description && <span className="form-help">{r.description}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {tab === 'ai' && (
        <div className="card">
          <div className="card-header"><div className="card-title">AI Provider Configuration</div></div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="alert alert-info">
              <CheckCircle size={16} />
              <div style={{ fontSize: '0.8125rem' }}>
                Currently using <strong>Groq API</strong> (llama-3.3-70b-versatile). To switch to Claude, set <code>AI_PROVIDER=claude</code> in your <code>.env</code> file.
              </div>
            </div>
            {[
              { label: 'AI Provider', key: 'AI_PROVIDER', placeholder: 'groq', help: 'groq or claude' },
              { label: 'Groq API Key', key: 'GROQ_API_KEY', placeholder: 'gsk_...', help: 'Get from console.groq.com' },
              { label: 'Large Model', key: 'GROQ_MODEL_LARGE', placeholder: 'llama-3.3-70b-versatile', help: 'Complex extraction and drafting' },
              { label: 'Fast Model', key: 'GROQ_MODEL_FAST', placeholder: 'llama-3.1-8b-instant', help: 'Fast classification tasks' },
            ].map(f => (
              <div key={f.key} className="form-group">
                <label className="form-label">{f.label}</label>
                <input className="form-input" placeholder={f.placeholder} disabled style={{ background: 'var(--gray-50)', color: 'var(--text-muted)' }} defaultValue={f.placeholder} />
                <span className="form-help">{f.help} — Edit in <code>.env</code> file</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'company' && (
        <div className="card">
          <div className="card-header"><div className="card-title">Company Information</div></div>
          <div className="card-body">
            <div className="alert alert-info" style={{ marginBottom: '1rem' }}>
              <CheckCircle size={16} />
              <span style={{ fontSize: '0.8125rem' }}>Company details are used in cover letter generation and Excel headers. Edit in <code>.env</code> file.</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'Company Name', key: 'COMPANY_NAME' },
                { label: 'Address', key: 'COMPANY_ADDRESS' },
                { label: 'Phone', key: 'COMPANY_PHONE' },
                { label: 'Email', key: 'COMPANY_EMAIL' },
                { label: 'Website', key: 'COMPANY_WEBSITE' },
                { label: 'Signatory Name', key: 'SIGNATORY_NAME' },
                { label: 'Signatory Title', key: 'SIGNATORY_TITLE' },
              ].map(f => (
                <div key={f.key} className="form-group">
                  <label className="form-label">{f.label}</label>
                  <input className="form-input" placeholder={`Set ${f.key} in .env`} disabled style={{ background: 'var(--gray-50)', color: 'var(--text-muted)' }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
