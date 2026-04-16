import { useState } from 'react'
import { Calculator, RefreshCw } from 'lucide-react'

type SectionType = 'plate' | 'pipe' | 'round_bar' | 'angle' | 'flat_bar'

const STEEL_DENSITY = 7850 // kg/m³

function calcWeight(type: SectionType, vals: any): { weight: number; formula: string } | null {
  const n = (k: string) => parseFloat(vals[k]) || 0
  try {
    if (type === 'plate' || type === 'flat_bar') {
      const L = n('length'), W = n('width'), T = n('thickness'), Qty = n('quantity') || 1
      if (!L || !W || !T) return null
      const vol = L * W * T / 1e9  // mm³ → m³
      const each = vol * STEEL_DENSITY
      const total = each * Qty
      return { weight: total, formula: `W = ${L}mm × ${W}mm × ${T}mm × 7850 / 1e9 × ${Qty} = ${total.toFixed(4)} kg` }
    }
    if (type === 'pipe') {
      const OD = n('od'), T = n('thickness'), L = n('length'), Qty = n('quantity') || 1
      if (!OD || !T || !L) return null
      const each = (OD - T) * T * L * 0.02466 / 1000
      const total = each * Qty
      return { weight: total, formula: `W = (OD${OD} - T${T}) × T${T} × L${L} × 0.02466 / 1000 × ${Qty} = ${total.toFixed(4)} kg` }
    }
    if (type === 'round_bar') {
      const D = n('diameter'), L = n('length'), Qty = n('quantity') || 1
      if (!D || !L) return null
      const area = Math.PI / 4 * D * D
      const vol = area * L / 1e9
      const total = vol * STEEL_DENSITY * Qty
      return { weight: total, formula: `W = π/4 × ${D}² × ${L} × 7850 / 1e9 × ${Qty} = ${total.toFixed(4)} kg` }
    }
    if (type === 'angle') {
      const L1 = n('leg1'), L2 = n('leg2'), T = n('thickness'), L = n('length'), Qty = n('quantity') || 1
      if (!L1 || !T || !L) return null
      const area = (L1 + (L2 || L1) - T) * T
      const vol = area * L / 1e9
      const total = vol * STEEL_DENSITY * Qty
      return { weight: total, formula: `W = (${L1}+${L2||L1}-${T}) × ${T} × ${L} × 7850 / 1e9 × ${Qty} = ${total.toFixed(4)} kg` }
    }
    return null
  } catch { return null }
}

const fields: Record<SectionType, { key: string; label: string; unit: string }[]> = {
  plate: [
    { key: 'length', label: 'Length', unit: 'mm' },
    { key: 'width', label: 'Width', unit: 'mm' },
    { key: 'thickness', label: 'Thickness', unit: 'mm' },
    { key: 'quantity', label: 'Quantity', unit: 'nos' },
  ],
  flat_bar: [
    { key: 'length', label: 'Length', unit: 'mm' },
    { key: 'width', label: 'Width', unit: 'mm' },
    { key: 'thickness', label: 'Thickness', unit: 'mm' },
    { key: 'quantity', label: 'Quantity', unit: 'nos' },
  ],
  pipe: [
    { key: 'od', label: 'Outer Diameter (OD)', unit: 'mm' },
    { key: 'thickness', label: 'Wall Thickness', unit: 'mm' },
    { key: 'length', label: 'Length', unit: 'mm' },
    { key: 'quantity', label: 'Quantity', unit: 'nos' },
  ],
  round_bar: [
    { key: 'diameter', label: 'Diameter', unit: 'mm' },
    { key: 'length', label: 'Length', unit: 'mm' },
    { key: 'quantity', label: 'Quantity', unit: 'nos' },
  ],
  angle: [
    { key: 'leg1', label: 'Leg 1', unit: 'mm' },
    { key: 'leg2', label: 'Leg 2', unit: 'mm' },
    { key: 'thickness', label: 'Thickness', unit: 'mm' },
    { key: 'length', label: 'Length', unit: 'mm' },
    { key: 'quantity', label: 'Quantity', unit: 'nos' },
  ],
}

const sectionTypes: { value: SectionType; label: string }[] = [
  { value: 'plate', label: 'Plate / Rectangular' },
  { value: 'pipe', label: 'Pipe / Hollow Section' },
  { value: 'round_bar', label: 'Round Bar / Rod' },
  { value: 'flat_bar', label: 'Flat Bar' },
  { value: 'angle', label: 'Angle Section (L)' },
]

export default function WeightCalculator() {
  const [type, setType] = useState<SectionType>('plate')
  const [vals, setVals] = useState<Record<string, string>>({ quantity: '1' })
  const [result, setResult] = useState<{ weight: number; formula: string } | null>(null)
  const [items, setItems] = useState<{ type: string; vals: any; weight: number }[]>([])

  const setVal = (k: string, v: string) => setVals(prev => ({ ...prev, [k]: v }))

  const calculate = () => {
    const r = calcWeight(type, vals)
    setResult(r)
  }

  const addToList = () => {
    if (!result) return
    setItems(prev => [...prev, {
      type,
      vals: { ...vals },
      weight: result.weight,
    }])
  }

  const reset = () => { setVals({ quantity: '1' }); setResult(null) }
  const totalWeight = items.reduce((s, it) => s + it.weight, 0)

  return (
    <div className="animate-fade-in" style={{ maxWidth: 860, margin: '0 auto' }}>
      <div className="page-title-bar">
        <div>
          <h1 className="page-title">Weight Calculator</h1>
          <p className="page-subtitle">Calculate steel weight by section type — deterministic formulas, no AI</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Input */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="card">
            <div className="card-header"><div className="card-title">Section Input</div></div>
            <div className="card-body">
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Section Type</label>
                <select className="form-select" value={type} onChange={e => { setType(e.target.value as SectionType); reset() }}>
                  {sectionTypes.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {fields[type].map(f => (
                  <div key={f.key} className="form-group">
                    <label className="form-label">{f.label} <span style={{ color: 'var(--text-muted)' }}>({f.unit})</span></label>
                    <input
                      type="number"
                      className="form-input"
                      value={vals[f.key] || ''}
                      onChange={e => setVal(f.key, e.target.value)}
                      min="0"
                      step="0.01"
                    />
                  </div>
                ))}
              </div>
              <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem' }}>
                <button className="btn btn-primary" onClick={calculate} style={{ flex: 1 }}>
                  <Calculator size={16} /> Calculate
                </button>
                <button className="btn btn-secondary btn-icon" onClick={reset} title="Reset">
                  <RefreshCw size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Formula info */}
          <div className="card" style={{ background: 'var(--gray-50)' }}>
            <div className="card-body">
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Formula Used</div>
              {type === 'plate' && <code style={{ fontSize: '0.8rem', color: 'var(--primary-700)' }}>W = L × W × T × 7850 / 1e9 (mm→kg)</code>}
              {type === 'pipe' && <code style={{ fontSize: '0.8rem', color: 'var(--primary-700)' }}>W = (OD - T) × T × L × 0.02466 / 1000</code>}
              {type === 'round_bar' && <code style={{ fontSize: '0.8rem', color: 'var(--primary-700)' }}>W = π/4 × D² × L × 7850 / 1e9</code>}
              {type === 'flat_bar' && <code style={{ fontSize: '0.8rem', color: 'var(--primary-700)' }}>W = L × W × T × 7850 / 1e9</code>}
              {type === 'angle' && <code style={{ fontSize: '0.8rem', color: 'var(--primary-700)' }}>W = (L1 + L2 - T) × T × L × 7850 / 1e9</code>}
              <div style={{ marginTop: 6, fontSize: '0.75rem', color: 'var(--text-muted)' }}>Steel density = 7850 kg/m³</div>
            </div>
          </div>
        </div>

        {/* Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {result ? (
            <div className="card">
              <div className="card-header"><div className="card-title">Result</div></div>
              <div className="card-body">
                <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                  <div style={{ fontSize: '3rem', fontWeight: 900, color: 'var(--primary-700)', letterSpacing: '-0.05em' }}>
                    {result.weight.toFixed(4)}
                  </div>
                  <div style={{ fontSize: '1rem', color: 'var(--text-muted)', fontWeight: 600 }}>kilograms</div>
                </div>
                <div style={{ background: 'var(--gray-50)', borderRadius: 'var(--radius-md)', padding: '0.75rem', marginTop: '0.75rem' }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase' }}>Calculation</div>
                  <code style={{ fontSize: '0.8rem', color: 'var(--primary-700)', wordBreak: 'break-all' }}>{result.formula}</code>
                </div>
                <button className="btn btn-success" onClick={addToList} style={{ width: '100%', marginTop: '1rem' }}>
                  + Add to Weight List
                </button>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="empty-state" style={{ paddingTop: '3rem' }}>
                <div className="empty-state-icon">⚖️</div>
                <h3>Enter dimensions</h3>
                <p>Fill in the section dimensions and click Calculate to get the steel weight.</p>
              </div>
            </div>
          )}

          {/* Running list */}
          {items.length > 0 && (
            <div className="card">
              <div className="card-header">
                <div className="card-title">Weight List</div>
                <span className="badge badge-primary">{items.length} items</span>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                <table className="data-table">
                  <thead><tr><th>#</th><th>Type</th><th className="text-right">Weight (kg)</th></tr></thead>
                  <tbody>
                    {items.map((it, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td>
                        <td>{sectionTypes.find(s => s.value === it.type)?.label}</td>
                        <td className="text-right">{it.weight.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={2} style={{ fontWeight: 700 }}>TOTAL</td>
                      <td className="text-right" style={{ fontWeight: 700 }}>{totalWeight.toFixed(4)} kg</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
