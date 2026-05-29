/**
 * GmailCallback — loaded inside the OAuth2 popup window.
 * Exchanges the authorization code for tokens via the backend,
 * then notifies the opener and closes itself.
 */
import { useEffect, useState } from 'react'
import { api } from '../api/client'

const REDIRECT_URI = `${window.location.origin}/gmail/callback`

export default function GmailCallback() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const error = params.get('error')

    if (error) {
      setStatus('error')
      setMessage(error === 'access_denied' ? 'Access denied. Please try again.' : error)
      return
    }

    if (!code) {
      setStatus('error')
      setMessage('No authorization code received.')
      return
    }

    api.post('/gmail/callback', { code, redirect_uri: REDIRECT_URI })
      .then(res => {
        setStatus('success')
        setMessage(`Connected: ${res.data.email_address}`)
        // BroadcastChannel is blocked by COOP when Google severs the opener.
        // localStorage events fire reliably across all same-origin windows.
        localStorage.setItem(
          'gmail-oauth-success',
          JSON.stringify({ email: res.data.email_address, mailboxId: res.data.mailbox_id, ts: Date.now() })
        )
        setTimeout(() => window.close(), 1500)
      })
      .catch(err => {
        const detail = err.response?.data?.detail || 'Connection failed. Please try again.'
        setStatus('error')
        setMessage(detail)
        localStorage.setItem('gmail-oauth-error', JSON.stringify({ error: detail, ts: Date.now() }))
      })
  }, [])

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'system-ui, sans-serif',
      background: '#f8fafc',
      padding: 32,
      textAlign: 'center',
    }}>
      {status === 'loading' && (
        <>
          <div style={{ width: 40, height: 40, border: '3px solid #e2e8f0', borderTopColor: '#6366f1', borderRadius: '50%', animation: 'spin 0.8s linear infinite', marginBottom: 20 }} />
          <p style={{ color: '#64748b', fontSize: 15 }}>Connecting your Gmail account…</p>
        </>
      )}
      {status === 'success' && (
        <>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
          <p style={{ color: '#166534', fontSize: 15, fontWeight: 600 }}>{message}</p>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 8 }}>This window will close automatically.</p>
        </>
      )}
      {status === 'error' && (
        <>
          <div style={{ fontSize: 48, marginBottom: 12 }}>❌</div>
          <p style={{ color: '#991b1b', fontSize: 15, fontWeight: 600 }}>Connection failed</p>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 8 }}>{message}</p>
          <button
            onClick={() => window.close()}
            style={{ marginTop: 20, padding: '8px 20px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}
          >
            Close
          </button>
        </>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
