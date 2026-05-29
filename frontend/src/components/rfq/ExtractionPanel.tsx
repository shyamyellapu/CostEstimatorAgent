import { useEffect, useState } from 'react'
import { Zap, Eye, CheckCircle, Clock, AlertCircle, RefreshCw, FileText } from 'lucide-react'
import { api } from '../../api/client'

interface Attachment {
  id: string
  original_filename: string
  file_category: string
  document_type: string
  extraction_status: string
  classification_confidence: number | null
}

interface LineItem {
  id: string
  line_number: string | null
  tag_number: string | null
  description: string | null
  material: string | null
  quantity: number | null
  unit: string | null
  confidence_score: number | null
  source_attachment_id: string | null
}

interface Props {
  rfqId: string
  attachments: Attachment[]
  onUpdate?: () => void
}

const extractionStatusIcon: Record<string, JSX.Element> = {
  pending:   <Clock size={13} color="#6b7280" />,
  running:   <RefreshCw size={13} color="#3b82f6" className="spin" />,
  completed: <CheckCircle size={13} color="#22c55e" />,
  failed:    <AlertCircle size={13} color="#ef4444" />,
}

export default function ExtractionPanel({ rfqId, attachments, onUpdate }: Props) {
  const [lineItems, setLineItems] = useState<LineItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedAttId, setSelectedAttId] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)

  const loadItems = async () => {
    try {
      const res = await api.get(`/rfq/${rfqId}/line-items`)
      setLineItems(res.data)
    } catch {/* handled */}
    setLoading(false)
  }

  useEffect(() => { loadItems() }, [rfqId])

  // Poll while any attachment is in "running" state
  useEffect(() => {
    const hasRunning = attachments.some(a => a.extraction_status === 'running')
    if (hasRunning && !polling) {
      setPolling(true)
      const interval = setInterval(async () => {
        await loadItems()
        onUpdate?.()
        const res = await api.get(`/rfq/${rfqId}/attachments`)
        const stillRunning = res.data.some((a: Attachment) => a.extraction_status === 'running')
        if (!stillRunning) {
          clearInterval(interval)
          setPolling(false)
        }
      }, 3000)
      return () => clearInterval(interval)
    }
  }, [attachments])

  const selectedItems = selectedAttId
    ? lineItems.filter(li => li.source_attachment_id === selectedAttId)
    : lineItems

  const totalWeight = selectedItems.reduce((s, li) => {
    if (li.quantity && (li as any).total_weight_kg) return s + (li as any).total_weight_kg
    return s
  }, 0)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16 }}>
      {/* Left panel: attachment list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            cursor: 'pointer',
            background: !selectedAttId ? 'var(--primary-50)' : 'transparent',
            borderColor: !selectedAttId ? 'var(--primary-300)' : 'var(--border)',
          }}
          onClick={() => setSelectedAttId(null)}
        >
          <div style={{ fontSize: 13, fontWeight: 600 }}>All Attachments</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {lineItems.length} total items extracted
          </div>
        </div>

        {attachments.map(att => {
          const count = lineItems.filter(li => li.source_attachment_id === att.id).length
          const isSelected = selectedAttId === att.id
          return (
            <div
              key={att.id}
              onClick={() => setSelectedAttId(isSelected ? null : att.id)}
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                border: `1px solid ${isSelected ? 'var(--primary-300)' : 'var(--border)'}`,
                cursor: 'pointer',
                background: isSelected ? 'var(--primary-50)' : 'transparent',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <FileText size={13} color="var(--text-muted)" />
                <span style={{ fontSize: 12, fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {att.original_filename}
                </span>
                {extractionStatusIcon[att.extraction_status] || extractionStatusIcon['pending']}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                <span>{att.document_type}</span>
                <span>{count} items</span>
              </div>
              {att.classification_confidence != null && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ height: 3, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                    <div style={{
                      width: `${att.classification_confidence * 100}%`,
                      height: '100%',
                      background: att.classification_confidence >= 0.85 ? '#22c55e' : att.classification_confidence >= 0.65 ? '#f59e0b' : '#ef4444',
                    }} />
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                    Class confidence: {(att.classification_confidence * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Right panel: extracted data preview */}
      <div>
        {polling && (
          <div style={{ padding: '10px 16px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
            <RefreshCw size={13} color="#3b82f6" className="spin" />
            Extraction in progress — auto-refreshing…
          </div>
        )}

        {loading ? (
          <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>Loading…</div>
        ) : selectedItems.length === 0 ? (
          <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
            <Zap size={36} style={{ marginBottom: 12, opacity: 0.3 }} />
            <p>No items extracted yet. Trigger extraction to process attachments.</p>
          </div>
        ) : (
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {selectedItems.length} extracted items
                {selectedAttId && ` from ${attachments.find(a => a.id === selectedAttId)?.original_filename}`}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Avg confidence: {(selectedItems.reduce((s, i) => s + (i.confidence_score ?? 0.75), 0) / selectedItems.length * 100).toFixed(0)}%
              </div>
            </div>
            <div style={{ overflow: 'auto', maxHeight: 500 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 1 }}>
                  <tr>
                    {['#', 'Tag', 'Description', 'Material', 'Qty', 'Unit', 'Confidence'].map(h => (
                      <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {selectedItems.map((item, idx) => {
                    const conf = item.confidence_score
                    const confColor = conf == null ? '#6b7280' : conf >= 0.85 ? '#22c55e' : conf >= 0.65 ? '#f59e0b' : '#ef4444'
                    return (
                      <tr key={item.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>{item.line_number || idx + 1}</td>
                        <td style={{ padding: '8px 12px', fontWeight: 500 }}>{item.tag_number || '—'}</td>
                        <td style={{ padding: '8px 12px', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.description || '—'}</td>
                        <td style={{ padding: '8px 12px', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>{item.material || '—'}</td>
                        <td style={{ padding: '8px 12px' }}>{item.quantity ?? '—'}</td>
                        <td style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>{item.unit || '—'}</td>
                        <td style={{ padding: '8px 12px' }}>
                          {conf != null && (
                            <span style={{ color: confColor, fontWeight: 600 }}>{(conf * 100).toFixed(0)}%</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
