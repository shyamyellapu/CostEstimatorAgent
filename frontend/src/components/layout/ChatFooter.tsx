import { useState, useRef, useEffect } from 'react'
import { Send, Bot, X, ChevronUp } from 'lucide-react'
import { api } from '../../api/client'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatFooter() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => Math.random().toString(36).slice(2))
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    const userMsg: Message = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    try {
      const res = await api.post('/chat', {
        messages: [...messages, userMsg],
        session_id: sessionId,
      })
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.response }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <>
      {/* Chat Panel */}
      {open && (
        <div style={{
          position: 'fixed', bottom: 70, left: 'var(--sidebar-width)', right: 0,
          maxWidth: 480, marginLeft: 'auto', marginRight: '1.5rem',
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-xl)',
          zIndex: 90,
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}>
          {/* Panel Header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.75rem',
            padding: '0.875rem 1.125rem',
            borderBottom: '1px solid var(--border)',
            background: 'var(--gray-50)',
          }}>
            <div style={{
              width: 32, height: 32,
              background: 'linear-gradient(135deg, var(--primary-600), var(--primary-800))',
              borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Bot size={16} color="white" />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>AI Assistant</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--success-600)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success-500)', display: 'inline-block' }} />
                Online · Powered by Groq
              </div>
            </div>
            <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setOpen(false)}>
              <X size={16} />
            </button>
          </div>

          {/* Messages */}
          <div className="chat-messages" style={{ flex: 1 }}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                <Bot size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>Ask me anything</div>
                <div style={{ fontSize: '0.8125rem', marginTop: 4 }}>
                  I can help with fabrication costing, member types, and calculations.
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble ${m.role}`}>
                {m.content}
              </div>
            ))}
            {loading && (
              <div className="chat-bubble assistant" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--gray-400)', animation: 'pulse 1s infinite' }} />
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--gray-400)', animation: 'pulse 1s 0.2s infinite' }} />
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--gray-400)', animation: 'pulse 1s 0.4s infinite' }} />
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>
      )}

      {/* Footer Bar */}
      <div className="chat-footer">
        <button
          className="btn btn-ghost btn-icon"
          onClick={() => setOpen(o => !o)}
          title="AI Assistant"
          style={{
            background: open ? 'var(--primary-50)' : undefined,
            color: open ? 'var(--primary-600)' : undefined,
          }}
        >
          <Bot size={18} />
        </button>
        <input
          className="chat-input"
          placeholder="Ask the AI Assistant anything about your estimate…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          onFocus={() => setOpen(true)}
        />
        <button
          className="btn btn-primary btn-icon"
          onClick={send}
          disabled={!input.trim() || loading}
          title="Send"
        >
          <Send size={16} />
        </button>
      </div>
    </>
  )
}
