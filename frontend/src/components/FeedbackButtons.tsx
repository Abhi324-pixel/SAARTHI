import { useState } from 'react'
import { apiT03, type FeedbackAction } from '../api_ext/T03'
import { useApp } from '../store'

interface FeedbackButtonsProps {
  conceptId: string
  context?: 'explanation' | 'task' | 'quiz'
  itemId?: string
  onAction?: (action: FeedbackAction, message: string, after?: any) => void
  label?: string
}

export default function FeedbackButtons({
  conceptId,
  context = 'explanation',
  itemId,
  onAction,
  label = 'Pacing & style:',
}: FeedbackButtonsProps) {
  const { me, toast, bump, setRoadmapNote } = useApp()
  const [busy, setBusy] = useState(false)
  const [clicked, setClicked] = useState<string | null>(null)

  const isHindi = me?.language === 'hindi'

  const labels = {
    too_easy: isHindi ? 'बहुत आसान' : 'Too easy',
    too_hard: isHindi ? 'बहुत मुश्किल' : 'Too hard',
    helpful: isHindi ? 'मदद मिली' : 'This helped',
  }

  async function send(signal: 'too_easy' | 'too_hard' | 'helpful') {
    if (busy) return
    setBusy(true)
    try {
      const res = await apiT03.feedback(conceptId, signal, context, itemId)
      setClicked(signal)
      toast(res.message)
      if (res.after?.roadmap?.changed) {
        setRoadmapNote(res.after.roadmap.change_reason)
      }
      bump()
      onAction?.(res.action, res.message, res.after)
      setTimeout(() => setClicked(null), 3000)
    } catch (e: any) {
      toast(e.message || 'Feedback not recorded', 'err')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap text-xs text-muted" id={`t03-feedback-${context}`}>
      {label && <span className="font-semibold text-[11px] mr-0.5">{label}</span>}
      <button
        id="t03-btn-too-easy"
        className={`btn btn-xs ${clicked === 'too_easy' ? 'btn-primary' : 'btn-ghost'}`}
        disabled={busy}
        onClick={() => send('too_easy')}
        title="Tell SAARTHI to challenge you with a harder question"
      >
        <span aria-hidden>⚡</span> {labels.too_easy}
      </button>
      <button
        id="t03-btn-too-hard"
        className={`btn btn-xs ${clicked === 'too_hard' ? 'btn-primary' : 'btn-ghost'}`}
        disabled={busy}
        onClick={() => send('too_hard')}
        title="Switch to a gentler explanation and check prerequisites"
      >
        <span aria-hidden>🧗</span> {labels.too_hard}
      </button>
      <button
        id="t03-btn-helpful"
        className={`btn btn-xs ${clicked === 'helpful' ? 'btn-primary' : 'btn-ghost'}`}
        disabled={busy}
        onClick={() => send('helpful')}
        title="Remember this teaching approach for future topics"
      >
        <span aria-hidden>👍</span> {labels.helpful}
      </button>
    </div>
  )
}
