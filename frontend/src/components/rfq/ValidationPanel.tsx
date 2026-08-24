import { useEffect, useState } from 'react'
import {
  AlertCircle, AlertTriangle, Info, CheckCircle, ChevronDown, ChevronUp, RefreshCw
} from 'lucide-react'
import { api } from '../../api/client'

interface ValidationIssue {
  id: string
  validation_type: string
  severity: string
  message: string
  field_name: string | null
  extracted_value: string | null
  suggested_value: string | null
  confidence: number | null
  is_resolved: boolean
  resolved_by: string | null
  resolution_note: string | null
}

interface Props {
  rfqId: string
  onUpdate?: () => void
}

const severityIcon = {
  error:   <AlertCircle size={15} color="#ef4444" />,
  warning: <AlertTriangle size={15} color="#f59e0b" />,
  info:    <Info size={15} color="#3b82f6" />,
}

const severityBg = {
  error:   '#fff1f2',
  warning: '#fffbeb',
  info:    '#eff6ff',
}

const severityBorder = {
  error:   '#fecaca',
  warning: '#fde68a',
  info:    '#bfdbfe',
}

export default function ValidationPanel({ rfqId, onUpdate }: Props) {
  const [data, setData] = useState<{ issues: ValidationIssue[]; errors: number; warnings: number; total: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [revalidating, setRevalidating] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [resolving, setResolving] = useState<string | null>(null)
  const [showResolved, setShowResolved] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get(`/rfq/${rfqId}/validation`)
      setData(res.data)
    } catch {/* handled */}
    setLoading(false)
  }

  useEffect(() => { load() }, [rfqId])

  const revalidate = async () => {
    setRevalidating(true)
    try {
      await api.post(`/rfq/${rfqId}/validate`)
      setTimeout(load, 2000)
    } catch {/* handled */}
    setRevalidating(false)
  }

  const resolve = async (issue: ValidationIssue) => {
    setResolving(issue.id)
    try {
      await api.post(`/rfq/${rfqId}/validation/${issue.id}/resolve`, {
        resolved_by: 'reviewer',
        resolution_note: 'Manually resolved',
      })
      await load()
      onUpdate?.()
    } catch {/* handled */}
    setResolving(null)
  }

  const toggleExpand = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>Loading validation…</div>
  if (!data) return null

  const visible = data.issues.filter(i => showResolved || !i.is_resolved)

  return (
    <div>
      {/* Summary bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div className="card" style={{ display: 'flex', gap: 20, padding: '12px 20px', flex: 1 }}>
          {[
            { label: 'Errors', count: data.errors, color: '#ef4444' },
            { label: 'Warnings', count: data.warnings, color: '#f59e0b' },
            { label: 'Info', count: data.total - data.errors - data.warnings, color: '#3b82f6' },
            { label: 'Resolved', count: data.issues.filter(i => i.is_resolved).length, color: '#22c55e' },
          ].map(s => (
            <div key={s.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: s.color }}>{s.count}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s.label}</div>
            </div>
          ))}
        </div>
        <button className="btn btn-secondary" onClick={revalidate} disabled={revalidating}>
          <RefreshCw size={14} className={revalidating ? 'spin' : ''} />
          {revalidating ? 'Revalidating…' : 'Re-validate'}
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showResolved}
            onChange={e => setShowResolved(e.target.checked)}
          />
          Show resolved issues
        </label>
      </div>

      {/* Issues list */}
      {visible.length === 0 ? (
        <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
          <CheckCircle size={36} style={{ marginBottom: 12, color: '#22c55e', opacity: 0.6 }} />
          <p>{data.total === 0 ? 'No validation issues found. Extraction looks good!' : 'All issues resolved.'}</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {visible.map(issue => {
            const sev = issue.severity as keyof typeof severityIcon
            const isExpanded = expanded.has(issue.id)
            return (
              <div
                key={issue.id}
                style={{
                  borderRadius: 8,
                  border: `1px solid ${issue.is_resolved ? 'var(--border)' : severityBorder[sev] || 'var(--border)'}`,
                  background: issue.is_resolved ? 'transparent' : severityBg[sev] || 'transparent',
                  overflow: 'hidden',
                  opacity: issue.is_resolved ? 0.65 : 1,
                }}
              >
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', cursor: 'pointer' }}
                  onClick={() => toggleExpand(issue.id)}
                >
                  {severityIcon[sev] || <Info size={15} />}
                  <span style={{ flex: 1, fontSize: 13 }}>{issue.message}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 8 }}>{issue.validation_type}</span>
                  {issue.is_resolved && <CheckCircle size={14} color="#22c55e" />}
                  {isExpanded ? <ChevronUp size={14} color="var(--text-muted)" /> : <ChevronDown size={14} color="var(--text-muted)" />}
                </div>

                {isExpanded && (
                  <div style={{ borderTop: '1px solid var(--border)', padding: '12px 16px', background: 'rgba(255,255,255,0.6)' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10, fontSize: 12 }}>
                      {issue.field_name && (
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Field: </span>
                          <span style={{ fontWeight: 600 }}>{issue.field_name}</span>
                        </div>
                      )}
                      {issue.extracted_value && (
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Extracted: </span>
                          <span style={{ fontFamily: 'monospace', background: '#f1f5f9', padding: '1px 6px', borderRadius: 4 }}>{issue.extracted_value}</span>
                        </div>
                      )}
                      {issue.suggested_value && (
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Suggested: </span>
                          <span style={{ fontFamily: 'monospace', background: '#dcfce7', padding: '1px 6px', borderRadius: 4 }}>{issue.suggested_value}</span>
                        </div>
                      )}
                      {issue.confidence != null && (
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Confidence: </span>
                          <span style={{ fontWeight: 600, color: issue.confidence < 0.65 ? '#ef4444' : '#22c55e' }}>
                            {(issue.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      )}
                    </div>
                    {issue.is_resolved ? (
                      <div style={{ fontSize: 12, color: '#22c55e' }}>
                        ✓ Resolved by {issue.resolved_by} — {issue.resolution_note}
                      </div>
                    ) : (
                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: 12, padding: '5px 14px' }}
                        onClick={() => resolve(issue)}
                        disabled={resolving === issue.id}
                      >
                        <CheckCircle size={12} />
                        {resolving === issue.id ? 'Resolving…' : 'Mark Resolved'}
                      </button>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
