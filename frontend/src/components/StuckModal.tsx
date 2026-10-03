import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../store'
import { MicButton } from './audio'
import { Callout, FlagChip } from './ui'

const CAUSE: Record<string, { label: string; tone: string }> = {
  misconception: { label: 'A mix-up in how it works', tone: '#7b1fa2' },
  prerequisite: { label: 'A missing building block', tone: '#8a4b00' },
  slip: { label: 'A small slip', tone: '#1f7a7a' },
  syntax: { label: 'A syntax problem', tone: '#1f7a7a' },
  unclear: { label: 'Not clear yet', tone: '#5b6675' },
}

export default function StuckModal() {
  const { stuckState, closeStuck, toast, setRoadmapNote, bump } = useApp()
  const nav = useNavigate()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [out, setOut] = useState<any | null>(null)

  useEffect(() => {
    if (stuckState.open) {
      setText(stuckState.prefill?.text ?? ''); setQuery(stuckState.prefill?.query ?? ''); setOut(null)
    }
  }, [stuckState.open, stuckState.prefill])
  if (!stuckState.open) return null

  async function go() {
    setBusy(true)
    try {
      const r = await api.stuck({ text, query: query || undefined, task_id: stuckState.prefill?.task_id, concept_id: stuckState.prefill?.concept_id })
      setOut(r)
      if (r.after?.roadmap?.changed) setRoadmapNote(r.after.roadmap.change_reason)
      bump()
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  async function askMentor() {
    try {
      const c = await api.createCase({ category: 'technical', concept_id: out?.concept_id, reason: out?.explanation || text, note: text, trigger: 'stuck_button' })
      closeStuck(); toast('Case opened — your mentor sees a full report.'); nav('/mentors/' + c.case_id)
    } catch (e: any) { toast(e.message, 'err') }
  }

  const cause = out ? CAUSE[out.cause] ?? CAUSE.unclear : null
  return (
    <div className="fixed inset-0 z-[60] bg-[rgba(5,14,22,0.75)] backdrop-blur-md flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-label="I'm stuck">
      <div className="border border-[rgba(210,225,235,0.22)] bg-[rgba(16,26,36,0.92)] backdrop-blur-2xl w-full sm:max-w-2xl rounded-t-3xl sm:rounded-3xl p-6 max-h-[92vh] overflow-auto shadow-2xl text-white">
        <div className="flex items-start justify-between">
          <div>
            <div className="eyebrow">Diagnostic Layer</div>
            <h2 className="text-xl font-extrabold text-white heading-glow mt-1">Let's find out <i>why</i> — not just the fix</h2>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={closeStuck} aria-label="Close">✕</button>
        </div>
        <div className="mt-4 space-y-3.5">
          <label className="block text-sm font-semibold text-slate-200 desc-glow">What's going wrong?
            <textarea className="input mt-1.5 min-h-[85px]" value={text} onChange={e => setText(e.target.value)} placeholder="e.g. my LEFT JOIN is dropping customers / I get 403 but I'm logged in" />
          </label>
          <div className="flex justify-end -mt-1"><MicButton onText={t => setText(p => (p ? p + ' ' : '') + t)} /></div>
          <label className="block text-sm font-semibold text-slate-200 desc-glow">Paste your SQL or error (optional)
            <textarea className="input mono mt-1.5 min-h-[90px] text-[13px]" value={query} onChange={e => setQuery(e.target.value)} spellCheck={false} />
          </label>
          <button className="btn btn-primary w-full" disabled={busy || (!text.trim() && !query.trim())} onClick={go}>
            {busy ? 'Analyzing your problem…' : 'Diagnose problem'}
          </button>
        </div>

        {out && cause && (
          <div className="mt-5 space-y-3.5 pop border-t border-[rgba(210,225,235,0.12)] pt-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="chip" style={{ background: 'rgba(25, 39, 51, 0.7)', color: cause.tone, border: '1px solid rgba(210, 225, 235, 0.2)' }}>Likely cause: {cause.label}</span>
              {out.concept_name && <span className="chip" style={{ background: 'rgba(77, 157, 255, 0.15)', color: '#4D9DFF', border: '1px solid rgba(77, 157, 255, 0.35)' }}>{out.concept_name}</span>}
              <span className="chip" style={{ background: 'rgba(210, 225, 235, 0.08)', color: '#AEBBC5' }}>via {out.source.replace('_', ' ')}</span>
            </div>
            <p className="text-sm text-slate-200 desc-glow leading-relaxed">{out.explanation}</p>
            {out.objective && (out.objective.error || out.objective.hints?.length > 0) && (
              <Callout tone="saffron" title="What the practice database said">{out.objective.error || out.objective.hints.join(' ')}</Callout>
            )}
            {out.misconception && (
              <Callout tone="violet" title={out.misconception.name}>
                <FlagChip flag="misconception" /> {out.misconception.description}
                {out.misconception.counter_example?.explanation && <div className="mt-1">{out.misconception.counter_example.explanation}</div>}
              </Callout>
            )}
            {out.prerequisite_name && <Callout tone="navy" title="Start here first">Revisit <b>{out.prerequisite_name}</b> — {out.concept_name} builds on it.</Callout>}
            {out.next_step && <div className="text-sm font-bold text-white heading-glow">Next step: <span className="font-medium text-slate-200">{out.next_step}</span></div>}
            <div className="flex gap-2.5 flex-wrap pt-2">
              {out.concept_id && <Link to={'/learn/' + (out.prerequisite_concept_id || out.concept_id)} className="btn btn-primary" onClick={closeStuck}>Open {out.prerequisite_name || out.concept_name}</Link>}
              <button className="btn btn-ghost" onClick={askMentor}>Ask a human mentor</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
