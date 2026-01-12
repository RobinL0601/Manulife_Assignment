import { useState, useEffect, useRef } from 'react'
import './ChatPanel.css'

const API_BASE = '/api/v1'

function ChatPanel({ jobId }) {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [isOpen, setIsOpen] = useState(false)
  const messagesEndRef = useRef(null)

  // Start chat session when panel is opened
  useEffect(() => {
    if (isOpen && !sessionId) {
      startSession()
    }
  }, [isOpen])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startSession = async () => {
    try {
      const response = await fetch(`${API_BASE}/chat/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to start chat')
      }

      const data = await response.json()
      setSessionId(data.session_id)
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || sending) return

    const userMessage = input.trim()
    setInput('')
    setSending(true)
    setError(null)

    // Add user message optimistically
    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    }])

    try {
      const response = await fetch(`${API_BASE}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to send message')
      }

      const data = await response.json()
      
      // Add assistant response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        quotes: data.relevant_quotes || [],
        confidence: data.confidence,
        timestamp: new Date().toISOString()
      }])
    } catch (err) {
      setError(err.message)
      // Remove optimistic user message on error
      setMessages(prev => prev.slice(0, -1))
    } finally {
      setSending(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (!isOpen) {
    return (
      <div className="chat-collapsed">
        <button className="chat-toggle-btn" onClick={() => setIsOpen(true)}>
          💬 Chat About This Contract
        </button>
      </div>
    )
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h3>💬 Chat About Contract</h3>
        <button className="chat-close-btn" onClick={() => setIsOpen(false)}>
          ✕
        </button>
      </div>

      {error && (
        <div className="chat-error">
          {error}
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <p>Ask questions about this contract.</p>
            <p className="chat-disclaimer">
              💡 Answers are derived only from the uploaded document using evidence-based retrieval.
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-message ${msg.role}`}>
            <div className="message-bubble">
              <div className="message-content">{msg.content}</div>
              
              {msg.role === 'assistant' && msg.quotes && msg.quotes.length > 0 && (
                <div className="message-citations">
                  <details>
                    <summary>📎 {msg.quotes.length} Citation(s)</summary>
                    <div className="citations-list">
                      {msg.quotes.map((quote, qIdx) => (
                        <div key={qIdx} className="citation-item">
                          <div className="citation-text">"{quote.text}"</div>
                          <div className="citation-pages">
                            Pages {quote.page_start}
                            {quote.page_end !== quote.page_start && `-${quote.page_end}`}
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              )}
              
              {msg.role === 'assistant' && msg.confidence !== undefined && (
                <div className="message-confidence">
                  Confidence: {msg.confidence}%
                </div>
              )}
            </div>
          </div>
        ))}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        <input
          type="text"
          className="chat-input"
          placeholder="Ask a question about this contract..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={sending || !sessionId}
          maxLength={1000}
        />
        <button
          className="chat-send-btn"
          onClick={sendMessage}
          disabled={!input.trim() || sending || !sessionId}
        >
          {sending ? '...' : 'Send'}
        </button>
      </div>
    </div>
  )
}

export default ChatPanel
