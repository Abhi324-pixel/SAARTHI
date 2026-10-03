import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiT07, type ChatAction } from '../api_ext/T07'
import { useApp } from '../store'
import { Spinner } from './ui'

interface Message {
  id: string
  role: 'learner' | 'mentor_ai'
  text: string
  actions?: ChatAction[]
  facts?: string[]
}

export default function ChatDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, toast } = useApp()
  const nav = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [sessionId, setSessionId] = useState<string | undefined>(undefined)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open && suggestions.length === 0) {
      apiT07.getSuggestions()
        .then(res => setSuggestions(res.suggestions || []))
        .catch(() => setSuggestions([]))
    }
  }, [open, suggestions.length])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  if (!open) return null

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim()
    if (!text || busy) return

    const userMsg: Message = {
      id: 'usr_' + Date.now(),
      role: 'learner',
      text,
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setBusy(true)

    try {
      const res = await apiT07.sendMessage(text, sessionId)
      if (res.session_id) setSessionId(res.session_id)

      const botMsg: Message = {
        id: 'bot_' + Date.now(),
        role: 'mentor_ai',
        text: res.reply,
        actions: res.actions,
        facts: res.facts_used,
      }
      setMessages(prev => [...prev, botMsg])
    } catch (err: any) {
      toast(err.message || 'Could not send message', 'err')
    } finally {
      setBusy(false)
    }
  }

  function handleAction(act: ChatAction) {
    if (act.type === 'concept' && act.concept_id) {
      nav(`/learn?concept=${encodeURIComponent(act.concept_id)}`)
      onClose()
    } else if (act.type === 'roadmap') {
      nav('/roadmap')
      onClose()
    } else if (act.type === 'genome') {
      nav('/genome')
      onClose()
    } else if (act.type === 'mentors' || act.type === 'open_case') {
      nav('/mentors')
      onClose()
    } else if (act.type === 'helpline') {
      window.location.href = 'tel:14416'
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-sm flex justify-end" role="dialog" aria-modal="true" aria-label="SAARTHI Assistant Chat">
      <div className="w-full max-w-md bg-white h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-4 border-b border-line flex items-center justify-between bg-paper/60">
          <div>
            <div className="eyebrow text-teal text-[11px]">Grounded Assistant</div>
            <h2 className="font-extrabold text-navy text-lg">{t('T07.chat.title')}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted hover:text-navy hover:bg-paper transition"
            aria-label="Close chat"
          >
            ✕
          </button>
        </div>

        {/* Message Log */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3" aria-live="polite">
          {messages.length === 0 && (
            <div className="text-center py-6 space-y-3">
              <div className="w-12 h-12 rounded-full bg-teal-soft text-teal font-extrabold flex items-center justify-center mx-auto text-xl">
                💬
              </div>
              <h3 className="font-bold text-navy text-sm">Ask about your plan, progress, or concepts</h3>
              <p className="text-xs text-muted max-w-xs mx-auto">
                SAARTHI answers from your personalized roadmap, evidence log, and curated curriculum notes.
              </p>
            </div>
          )}

          {/* Suggestions chips */}
          {messages.length === 0 && suggestions.length > 0 && (
            <div className="space-y-1.5 pt-2">
              <div className="text-[11px] font-bold text-muted uppercase tracking-wider">Suggested questions:</div>
              <div className="flex flex-col gap-1.5">
                {suggestions.map((sug, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(sug)}
                    className="text-left text-xs bg-paper hover:bg-teal-soft hover:text-teal font-medium p-2.5 rounded-xl border border-line transition text-navy"
                  >
                    💡 {sug}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(m => (
            <div
              key={m.id}
              className={`flex flex-col ${m.role === 'learner' ? 'items-end' : 'items-start'}`}
            >
              <div translate={m.role === 'learner' ? 'no' : undefined}
                className={`text-sm rounded-2xl px-4 py-2.5 max-w-[88%] shadow-sm ${
                  m.role === 'learner'
                    ? 'bg-navy text-white rounded-br-none'
                    : 'bg-paper text-navy border border-line rounded-bl-none'
                }`}
              >
                {m.text}
              </div>

              {/* Bot actions */}
              {m.actions && m.actions.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2 max-w-[88%]">
                  {m.actions.map((act, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleAction(act)}
                      className="chip text-xs bg-teal-soft text-teal hover:bg-teal hover:text-white font-bold transition shadow-sm border border-teal/20"
                    >
                      → {act.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}

          {busy && (
            <div className="flex items-center gap-2 text-xs text-muted bg-paper p-2.5 rounded-xl w-fit border border-line">
              <Spinner />
              <span>Thinking with your learning data…</span>
            </div>
          )}
          <div ref={scrollRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3 border-t border-line bg-paper/30 space-y-2">
          <form
            onSubmit={e => {
              e.preventDefault()
              handleSend()
            }}
            className="flex gap-2"
          >
            <input
              type="text"
              className="input flex-1 text-sm bg-white"
              placeholder="Ask why a topic is scheduled, what's next..."
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={busy}
              maxLength={1000}
              aria-label="Ask SAARTHI a question"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="btn btn-primary px-4 py-2 text-sm font-bold"
            >
              Send
            </button>
          </form>
          <div className="text-[11px] text-muted text-center">
            Answers come from your plan and SAARTHI's curated notes.
          </div>
        </div>
      </div>
    </div>
  )
}
