import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiT07, type ChatAction } from '../api_ext/T07'
import { useApp } from '../store'
import { Spinner } from './ui'
import { Sparkles, Send, X, Bot, ArrowRight, Lightbulb, MessageSquare } from 'lucide-react'

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
    <div
      className="fixed inset-0 z-50 overflow-hidden bg-[rgba(5,14,22,0.72)] backdrop-blur-md flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label="SAARTHI Assistant Chat"
    >
      <div className="w-full sm:max-w-md bg-[rgba(10,18,28,0.94)] backdrop-blur-2xl border-l border-[rgba(210,225,235,0.16)] h-full flex flex-col shadow-[-16px_0_40px_rgba(0,0,0,0.55)] text-white animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-4 sm:px-5 sm:py-4 border-b border-[rgba(210,225,235,0.12)] flex items-center justify-between bg-[rgba(14,24,36,0.75)] backdrop-blur-xl">
          <div>
            <div className="text-[11px] font-bold tracking-wider uppercase text-[var(--accent-orange)] flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
              <span>Grounded Assistant</span>
            </div>
            <h2 className="font-extrabold text-white text-lg tracking-tight heading-glow mt-0.5">
              {t('T07.chat.title')}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10 transition-all cursor-pointer"
            aria-label="Close chat"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Message Log */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4" aria-live="polite">
          {messages.length === 0 && (
            <div className="text-center py-8 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-[rgba(255,138,36,0.15)] border border-[rgba(255,138,36,0.30)] text-[var(--accent-orange)] flex items-center justify-center mx-auto text-xl shadow-[0_0_16px_rgba(255,138,36,0.18)]">
                <MessageSquare className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-white text-sm heading-glow">Ask about your plan, progress, or concepts</h3>
              <p className="text-xs text-[var(--text-muted)] max-w-xs mx-auto desc-glow leading-relaxed">
                SAARTHI answers from your personalized roadmap, evidence log, and curated curriculum notes.
              </p>
            </div>
          )}

          {/* Suggestions chips */}
          {messages.length === 0 && suggestions.length > 0 && (
            <div className="space-y-2 pt-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
                <Lightbulb className="w-3 h-3 text-[var(--accent-orange)]" />
                <span>Suggested questions:</span>
              </div>
              <div className="flex flex-col gap-2">
                {suggestions.map((sug, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(sug)}
                    className="text-left text-xs bg-[rgba(18,30,42,0.55)] hover:bg-[rgba(255,138,36,0.14)] hover:border-[rgba(255,138,36,0.35)] hover:text-white font-medium p-3 rounded-xl border border-[rgba(210,225,235,0.14)] transition-all text-slate-200 desc-glow flex items-center justify-between group cursor-pointer"
                  >
                    <span>💡 {sug}</span>
                    <ArrowRight className="w-3 h-3 opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 text-[var(--accent-orange)] transition-all shrink-0 ml-2" />
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
              {m.role === 'mentor_ai' && (
                <div className="flex items-center gap-1.5 mb-1 text-[11px] font-bold text-[var(--accent-orange)] pl-1">
                  <Bot className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
                  <span className="tracking-wide">SAARTHI</span>
                </div>
              )}

              <div
                translate={m.role === 'learner' ? 'no' : undefined}
                className={`text-sm rounded-2xl px-4 py-3 max-w-[88%] leading-relaxed ${
                  m.role === 'learner'
                    ? 'bg-gradient-to-r from-[rgba(255,138,36,0.24)] to-[rgba(255,138,36,0.14)] border border-[rgba(255,138,36,0.48)] text-white rounded-br-sm shadow-[0_4px_16px_rgba(255,138,36,0.16),inset_0_1px_0_rgba(255,255,255,0.18)] desc-glow'
                    : 'bg-[rgba(20,32,46,0.68)] hover:bg-[rgba(22,36,52,0.78)] backdrop-blur-md border border-[rgba(210,225,235,0.15)] text-slate-100 rounded-bl-sm shadow-[0_4px_20px_rgba(0,0,0,0.22),inset_0_1px_0_rgba(255,255,255,0.06)] desc-glow transition-colors'
                }`}
              >
                {m.text}
              </div>

              {/* Bot actions */}
              {m.actions && m.actions.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2 max-w-[88%]">
                  {m.actions.map((act, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleAction(act)}
                      className="group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[rgba(77,157,255,0.14)] hover:bg-[rgba(77,157,255,0.24)] text-[#79B7FF] hover:text-white border border-[rgba(77,157,255,0.32)] shadow-[0_2px_12px_rgba(77,157,255,0.14),inset_0_1px_0_rgba(255,255,255,0.08)] transition-all cursor-pointer"
                    >
                      <span>{act.label}</span>
                      <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}

          {busy && (
            <div className="flex items-center gap-2.5 text-xs text-slate-300 bg-[rgba(18,30,42,0.65)] px-3.5 py-2.5 rounded-xl border border-[rgba(210,225,235,0.15)] shadow-md w-fit">
              <Spinner />
              <span className="desc-glow">Thinking with your learning data…</span>
            </div>
          )}
          <div ref={scrollRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3.5 sm:p-4 border-t border-[rgba(210,225,235,0.14)] bg-[rgba(12,22,34,0.80)] backdrop-blur-xl space-y-2">
          <form
            onSubmit={e => {
              e.preventDefault()
              handleSend()
            }}
            className="flex gap-2"
          >
            <input
              type="text"
              className="input flex-1 text-sm bg-[rgba(16,28,42,0.65)] border-[rgba(210,225,235,0.18)] focus:border-[var(--accent-orange)] text-white placeholder:text-[var(--text-muted)] rounded-xl px-3.5 py-2.5 transition-all shadow-inner"
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
              className="btn btn-primary py-2.5 px-4 text-xs sm:text-sm font-bold flex items-center gap-1.5 shadow-[0_4px_16px_rgba(255,138,36,0.35)] hover:shadow-[0_6px_22px_rgba(255,138,36,0.50)] transition-all cursor-pointer"
            >
              <span>Send</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
          <div className="text-[11px] text-[var(--text-muted)] text-center desc-glow">
            Answers come from your plan and SAARTHI's curated notes.
          </div>
        </div>
      </div>
    </div>
  )
}
