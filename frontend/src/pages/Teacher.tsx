import { useEffect, useState } from 'react'
import { api, req } from '../api'
import { useApp } from '../store'
import { DemoBadge, SectionTitle, Spinner } from '../components/ui'

const COL: Record<string, string> = { unknown: '#FF5364', developing: '#FFB52E', proficient: '#4D9DFF', mastered: '#35D07F' }

export default function Teacher() {
  const { toast } = useApp()
  const [d, setD] = useState<any | null>(null)
  const [mem, setMem] = useState<{ member: boolean; joined: number; min_learners: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const load = () => { api.cohort().then(setD); req('/cohort/membership').then(setMem).catch(() => {}) }
  useEffect(() => { load() }, [])

  async function toggle() {
    setBusy(true)
    try { await req('/cohort/membership', { method: mem?.member ? 'DELETE' : 'POST' }); load() } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  if (!d) return <div className="py-20 flex justify-center"><Spinner label="Loading class view…" /></div>

  const joinBox = mem && (
    <div className="card p-5 space-y-2 max-w-3xl">
      <div className="eyebrow">Your choice</div>
      <p className="text-sm text-muted">{mem.member ? 'Your progress is included in this anonymous view. It is never shown with your name.' : 'You can include your progress in this view. It is anonymous: your name is never shown, and nothing about the group appears until enough people have joined.'}</p>
      <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={toggle}>{mem.member ? 'Remove me from the class view' : 'Include my progress (anonymous)'}</button>
    </div>
  )

  if (d.hidden) return (
    <div className="space-y-6">
      <div className="card p-6 lg:p-8"><div className="eyebrow">Class view</div><h1 className="h-page mt-1">{d.name}</h1></div>
      <div className="card p-6 space-y-2 max-w-3xl">
        <b className="text-white text-lg">Not enough learners yet</b>
        <p className="text-sm text-slate-300">{d.n_learners} of {d.min_learners} learners have joined. {d.privacy_note}</p>
        <p className="text-sm text-slate-300">This view will show where learners as a group stand and which misconceptions are most common. It uses only real learners who chose to be included, and no made-up data.</p>
      </div>
      {joinBox}
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="card p-6 lg:p-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="eyebrow">Class view · anonymous</div>
          <h1 className="h-page mt-1">{d.name}</h1>
          <p className="text-slate-300 desc-glow mt-2 max-w-3xl leading-relaxed">
            Which ideas does the whole class get wrong? A score can't tell you — misconceptions can. {d.n_learners} learners · aggregated, no transcripts.
          </p>
        </div>
        {d.is_mock && <DemoBadge label="demo class" title="Synthetic cohort generated for the demo. A real cohort uses the same code over real learners." />}
      </div>

      {joinBox}

      <div className="grid lg:grid-cols-12 gap-5">
        <div className="card p-6 lg:col-span-8 min-w-0">
          <SectionTitle eyebrow="Concept heat-map" title="Where the class stands" />
          <div className="space-y-3 mt-3">
            {d.concepts.map((c: any) => {
              const tot = Object.values(c.levels).reduce((a: number, b: any) => a + b, 0) as number || 1
              return (
                <div key={c.concept_id} className="grid grid-cols-[180px_1fr_48px] items-center gap-3 text-sm">
                  <span className="font-semibold text-white truncate" title={c.name}>{c.name}</span>
                  <div className="flex h-5 rounded-md overflow-hidden bg-[rgba(210,225,235,0.10)]" role="img" aria-label={Object.entries(c.levels).map(([k, v]) => `${v} ${k}`).join(', ')}>
                    {(['unknown', 'developing', 'proficient', 'mastered'] as const).map(k => c.levels[k] > 0 && (
                      <div key={k} title={`${c.levels[k]} ${k}`} style={{ width: `${(c.levels[k] / tot) * 100}%`, background: COL[k] }} />
                    ))}
                  </div>
                  <span className="text-xs text-slate-400 font-mono text-right">{Math.round(c.avg_p * 100)}%</span>
                </div>
              )
            })}
          </div>
          <div className="flex gap-4 mt-4 pt-3 border-t border-[rgba(210,225,235,0.10)] text-xs text-slate-300 font-semibold desc-glow">
            {Object.entries(COL).map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-1.5">
                <span className="h-3 w-3 rounded" style={{ background: v }} />
                {k === 'unknown' ? 'needs work' : k}
              </span>
            ))}
          </div>
        </div>

        <div className="lg:col-span-4 space-y-5">
          <div className="card p-5">
            <SectionTitle eyebrow="Most common" title="Class-wide misconceptions" />
            <ul className="space-y-3 mt-2">
              {d.top_misconceptions.map((m: any) => (
                <li key={m.misconception_id}>
                  <div className="flex justify-between text-sm font-bold text-white">
                    <span>{m.name}</span>
                    <span className="text-[#C084FC]">{m.count} learners</span>
                  </div>
                  <div className="text-xs text-slate-400 desc-glow mt-0.5">{m.concept_name} · {Math.round(m.share * 100)}% of class</div>
                  <div className="h-1.5 rounded-full bg-[rgba(210,225,235,0.10)] mt-1.5">
                    <div className="h-full rounded-full bg-[#A855F7]" style={{ width: `${m.share * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
            <p className="text-xs text-slate-400 desc-glow mt-4 pt-2 border-t border-[rgba(210,225,235,0.10)]">
              Teaching tip: a 10-minute "contrasting cases" demo on the top item usually fixes more than re-teaching the whole unit.
            </p>
          </div>

          <div className="card p-5">
            <SectionTitle eyebrow="Needs attention" title="Learners who may need help" />
            <ul className="space-y-2 mt-2">
              {d.needs_attention.map((n: any) => (
                <li key={n.ref} className="glass-row px-3 py-2 text-sm">
                  <b className="text-white">{n.display_name}</b>
                  <div className="text-xs text-slate-400 desc-glow mt-0.5">{n.reason}</div>
                </li>
              ))}
              {!d.needs_attention.length && <li className="text-sm text-slate-400 desc-glow">Nobody flagged.</li>}
            </ul>
            <p className="text-[11px] text-slate-500 desc-glow mt-3">{d.privacy_note}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
