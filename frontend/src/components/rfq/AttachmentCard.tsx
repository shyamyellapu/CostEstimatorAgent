import { useState } from 'react'
import {
  FileText, FileSpreadsheet, File, Image, Archive,
  Zap, RefreshCw, Eye, CheckCircle, Clock, AlertCircle
} from 'lucide-react'
import { api } from '../../api/client'

interface Attachment {
  id: string
  original_filename: string
  file_category: string
  document_type: string
  classification_confidence: number | null
  extraction_status: string
  revision_number: string | null
  document_number: string | null
  file_size: number | null
  storage_url: string | null
  created_at: string
}

interface Props {
  attachment: Attachment
  rfqId: string
  onUpdate: () => void
}

const categoryIcon: Record<string, JSX.Element> = {
  pdf:   <FileText size={18} color="#ef4444" />,
  excel: <FileSpreadsheet size={18} color="#22c55e" />,
  word:  <FileText size={18} color="#3b82f6" />,
  dwg:   <File size={18} color="#8b5cf6" />,
  zip:   <Archive size={18} color="#f59e0b" />,
  image: <Image size={18} color="#06b6d4" />,
}

const documentTypeLabel: Record<string, string> = {
  bom: 'Bill of Materials',
  pid: 'P&ID',
  ga_drawing: 'GA Drawing',
  isometric: 'Isometric',
  datasheet: 'Data Sheet',
  specification: 'Specification',
  rfq: 'RFQ Document',
  cover_letter: 'Cover Letter',
  drawing: 'Drawing',
  other: 'Unknown',
  unknown: 'Unclassified',
}

const extractionStatusConfig: Record<string, { color: string; icon: JSX.Element; label: string }> = {
  pending:   { color: '#6b7280', icon: <Clock size={12} />,         label: 'Pending' },
  running:   { color: '#3b82f6', icon: <RefreshCw size={12} className="spin" />, label: 'Extracting…' },
  completed: { color: '#22c55e', icon: <CheckCircle size={12} />,   label: 'Extracted' },
  failed:    { color: '#ef4444', icon: <AlertCircle size={12} />,   label: 'Failed' },
}

function formatBytes(bytes: number | null) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function AttachmentCard({ attachment: att, rfqId, onUpdate }: Props) {
  const [reclassifying, setReclassifying] = useState(false)
  const [reextracting, setReextracting] = useState(false)

  const reclassify = async () => {
    setReclassifying(true)
    try {
      await api.post(`/rfq/${rfqId}/attachments/${att.id}/reclassify`)
      onUpdate()
    } catch {/* handled */}
    setReclassifying(false)
  }

  const reextract = async () => {
    setReextracting(true)
    try {
      await api.post(`/rfq/${rfqId}/attachments/${att.id}/re-extract`)
      onUpdate()
    } catch {/* handled */}
    setReextracting(false)
  }

  const catIcon = categoryIcon[att.file_category] || <File size={18} color="#6b7280" />
  const extStatus = extractionStatusConfig[att.extraction_status] || extractionStatusConfig['pending']
  const conf = att.classification_confidence
  const confColor = conf == null ? '#6b7280' : conf >= 0.85 ? '#22c55e' : conf >= 0.65 ? '#f59e0b' : '#ef4444'

  return (
    <div className="card" style={{ padding: '16px 18px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 12 }}>
        <div style={{ flexShrink: 0, marginTop: 2 }}>{catIcon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {att.original_filename}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {formatBytes(att.file_size)}
          </div>
        </div>
      </div>

      {/* Classification */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: 'var(--text-muted)' }}>Type</span>
          <span style={{ fontWeight: 500 }}>{documentTypeLabel[att.document_type] || att.document_type}</span>
        </div>
        {att.revision_number && (
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: 'var(--text-muted)' }}>Revision</span>
            <span style={{ fontWeight: 500, background: '#dbeafe', color: '#1d4ed8', padding: '1px 6px', borderRadius: 4 }}>Rev {att.revision_number}</span>
          </div>
        )}
        {att.document_number && (
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: 'var(--text-muted)' }}>Doc #</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{att.document_number}</span>
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: 'var(--text-muted)' }}>Confidence</span>
          <span style={{ fontWeight: 600, color: confColor }}>
            {conf != null ? `${(conf * 100).toFixed(0)}%` : '—'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, alignItems: 'center' }}>
          <span style={{ color: 'var(--text-muted)' }}>Extraction</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: extStatus.color, fontWeight: 500 }}>
            {extStatus.icon} {extStatus.label}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {att.storage_url && (() => {
          const absoluteUrl = att.storage_url.startsWith('http')
            ? att.storage_url
            : att.storage_url
          return (
            <a
              href={absoluteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
              style={{ fontSize: 11, padding: '4px 10px', textDecoration: 'none' }}
            >
              <Eye size={12} /> View
            </a>
          )
        })()}
        <button
          className="btn btn-secondary"
          style={{ fontSize: 11, padding: '4px 10px' }}
          onClick={reclassify}
          disabled={reclassifying}
        >
          <RefreshCw size={12} className={reclassifying ? 'spin' : ''} />
          {reclassifying ? '…' : 'Reclassify'}
        </button>
        <button
          className="btn btn-secondary"
          style={{ fontSize: 11, padding: '4px 10px' }}
          onClick={reextract}
          disabled={reextracting}
        >
          <Zap size={12} />
          {reextracting ? '…' : 'Re-extract'}
        </button>
      </div>
    </div>
  )
}
