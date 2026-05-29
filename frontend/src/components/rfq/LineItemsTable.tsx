import { useEffect, useState } from 'react'
import { Edit2, Check, X, AlertCircle, CheckCircle, Trash2 } from 'lucide-react'
import { api } from '../../api/client'

interface LineItem {
  id: string
  line_number: string | null
  tag_number: string | null
  description: string | null
  material: string | null
  material_grade: string | null
  quantity: number | null
  unit: string | null
  weight_each_kg: number | null
  total_weight_kg: number | null
  pressure_class: string | null
  drawing_reference: string | null
  confidence_score: number | null
  is_confirmed: boolean
  confirmed_by: string | null
}

interface Props {
  rfqId: string
  canEdit?: boolean
  onUpdate?: () => void
}

export default function LineItemsTable({ rfqId, canEdit = true, onUpdate }: Props) {
  const [items, setItems] = useState<LineItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<Partial<LineItem>>({})
  const [saving, setSaving] = useState(false)
  const [confirmingAll, setConfirmingAll] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get(`/rfq/${rfqId}/line-items`)
      setItems(res.data)
    } catch {/* handled */}
    setLoading(false)
  }

  useEffect(() => { load() }, [rfqId])

  const startEdit = (item: LineItem) => {
    setEditingId(item.id)
    setEditForm({ ...item })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditForm({})
  }

  const saveEdit = async () => {
    if (!editingId) return
    setSaving(true)
    try {
      await api.put(`/rfq/${rfqId}/line-items/${editingId}`, editForm)
      await load()
      onUpdate?.()
      setEditingId(null)
    } catch {/* handled */}
    setSaving(false)
  }

  const confirmItem = async (item: LineItem) => {
    await api.put(`/rfq/${rfqId}/line-items/${item.id}`, { is_confirmed: true })
    await load()
    onUpdate?.()
  }

  const deleteItem = async (item: LineItem) => {
    if (!confirm(`Delete line item "${item.description || item.line_number}"?`)) return
    await api.delete(`/rfq/${rfqId}/line-items/${item.id}`)
    await load()
    onUpdate?.()
  }

  const confirmAll = async () => {
    setConfirmingAll(true)
    await api.post(`/rfq/${rfqId}/line-items/confirm-all`)
    await load()
    onUpdate?.()
    setConfirmingAll(false)
  }

  const unconfirmed = items.filter(i => !i.is_confirmed).length
  const lowConf = items.filter(i => (i.confidence_score ?? 1) < 0.75).length

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>Loading line items…</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 12, fontSize: 13 }}>
          <span style={{ color: 'var(--text-muted)' }}>{items.length} items</span>
          {unconfirmed > 0 && <span style={{ color: '#f59e0b' }}>· {unconfirmed} unconfirmed</span>}
          {lowConf > 0 && <span style={{ color: '#ef4444' }}>· {lowConf} low confidence</span>}
        </div>
        {canEdit && unconfirmed > 0 && (
          <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={confirmAll} disabled={confirmingAll}>
            <CheckCircle size={13} /> {confirmingAll ? 'Confirming…' : `Confirm All (${unconfirmed})`}
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
          No line items extracted. Run extraction on the attachments first.
        </div>
      ) : (
        <div className="card" style={{ overflow: 'auto', padding: 0 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
                {['#', 'Tag', 'Description', 'Material', 'Qty', 'Unit', 'Wt/ea (kg)', 'Total Wt', 'Pressure Class', 'Drg Ref', 'Conf', 'Status', canEdit ? 'Actions' : ''].filter(Boolean).map(h => (
                  <th key={h} style={{ padding: '9px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.3px', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => {
                const conf = item.confidence_score
                const confColor = conf == null ? '#6b7280' : conf >= 0.85 ? '#22c55e' : conf >= 0.65 ? '#f59e0b' : '#ef4444'
                const isEditing = editingId === item.id

                if (isEditing) {
                  return (
                    <tr key={item.id} style={{ background: '#fef9c3', borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 48 }} value={editForm.line_number ?? ''} onChange={e => setEditForm(p => ({ ...p, line_number: e.target.value }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 80 }} value={editForm.tag_number ?? ''} onChange={e => setEditForm(p => ({ ...p, tag_number: e.target.value }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 240 }} value={editForm.description ?? ''} onChange={e => setEditForm(p => ({ ...p, description: e.target.value }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 140 }} value={editForm.material ?? ''} onChange={e => setEditForm(p => ({ ...p, material: e.target.value }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 64 }} type="number" value={editForm.quantity ?? ''} onChange={e => setEditForm(p => ({ ...p, quantity: Number(e.target.value) }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 64 }} value={editForm.unit ?? ''} onChange={e => setEditForm(p => ({ ...p, unit: e.target.value }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 80 }} type="number" value={editForm.weight_each_kg ?? ''} onChange={e => setEditForm(p => ({ ...p, weight_each_kg: Number(e.target.value) }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 80 }} type="number" value={editForm.total_weight_kg ?? ''} onChange={e => setEditForm(p => ({ ...p, total_weight_kg: Number(e.target.value) }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 100 }} value={editForm.pressure_class ?? ''} onChange={e => setEditForm(p => ({ ...p, pressure_class: e.target.value }))} />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input className="form-input" style={{ width: 100 }} value={editForm.drawing_reference ?? ''} onChange={e => setEditForm(p => ({ ...p, drawing_reference: e.target.value }))} />
                      </td>
                      <td />
                      <td />
                      <td style={{ padding: '8px 12px' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn btn-primary" style={{ padding: '4px 10px', fontSize: 11 }} onClick={saveEdit} disabled={saving}>
                            <Check size={12} />
                          </button>
                          <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }} onClick={cancelEdit}>
                            <X size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                }

                return (
                  <tr
                    key={item.id}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      background: item.is_confirmed ? 'transparent' : (conf != null && conf < 0.65) ? '#fff1f2' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '9px 12px', color: 'var(--text-muted)' }}>{item.line_number || idx + 1}</td>
                    <td style={{ padding: '9px 12px', fontWeight: 500 }}>{item.tag_number || '—'}</td>
                    <td style={{ padding: '9px 12px', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.description || '—'}</td>
                    <td style={{ padding: '9px 12px', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.material || '—'}</td>
                    <td style={{ padding: '9px 12px' }}>{item.quantity ?? '—'}</td>
                    <td style={{ padding: '9px 12px', color: 'var(--text-muted)' }}>{item.unit || '—'}</td>
                    <td style={{ padding: '9px 12px' }}>{item.weight_each_kg?.toFixed(2) ?? '—'}</td>
                    <td style={{ padding: '9px 12px', fontWeight: 500 }}>{item.total_weight_kg?.toFixed(2) ?? '—'}</td>
                    <td style={{ padding: '9px 12px', color: 'var(--text-muted)' }}>{item.pressure_class || '—'}</td>
                    <td style={{ padding: '9px 12px', color: 'var(--text-muted)' }}>{item.drawing_reference || '—'}</td>
                    <td style={{ padding: '9px 12px' }}>
                      {conf != null && (
                        <span style={{ color: confColor, fontWeight: 600 }}>{(conf * 100).toFixed(0)}%</span>
                      )}
                    </td>
                    <td style={{ padding: '9px 12px' }}>
                      {item.is_confirmed
                        ? <span style={{ color: '#22c55e', fontSize: 11, fontWeight: 600 }}>✓ Confirmed</span>
                        : <span style={{ color: '#f59e0b', fontSize: 11 }}>Pending</span>
                      }
                    </td>
                    {canEdit && (
                      <td style={{ padding: '9px 12px' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}
                            onClick={() => startEdit(item)}
                            title="Edit"
                          >
                            <Edit2 size={13} />
                          </button>
                          {!item.is_confirmed && (
                            <button
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#22c55e', padding: 4 }}
                              onClick={() => confirmItem(item)}
                              title="Confirm"
                            >
                              <CheckCircle size={13} />
                            </button>
                          )}
                          <button
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: 4 }}
                            onClick={() => deleteItem(item)}
                            title="Delete"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr style={{ background: 'var(--bg-secondary)', borderTop: '2px solid var(--border)' }}>
                <td colSpan={7} style={{ padding: '9px 12px', fontWeight: 600, fontSize: 12 }}>Totals</td>
                <td style={{ padding: '9px 12px', fontWeight: 700 }}>
                  {items.reduce((sum, i) => sum + (i.total_weight_kg ?? 0), 0).toFixed(2)} kg
                </td>
                <td colSpan={canEdit ? 5 : 4} />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  )
}
