import { useEffect, useState } from 'react'
import { api, req } from '../api'
import { useApp } from '../store'
import { DemoBadge, SectionTitle, Spinner } from '../components/ui'

const COL: Record<string, string> = { unknown: '#c62828', developing: '#e0a100', proficient: '#2e8b57', mastered: '#1b5e20' }

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

  if (!d) return <div className="py-16 flex justify-center"><Spinner /></div>

  const joinBox = mem && (
    <div className="card p-5 space-y-2 max-w-3xl">
      <div className="eyebrow">Your choice</div>
      <p className="text-sm text-muted">{mem.member ? 'Your progress is included in this anonymous view. It is never shown with your name.' : 'You can include your progress in this view. It is anonymous: your name is never shown, and nothing about the group appears until enough people have joined.'}</p>
      <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={toggle}>{mem.member ? 'Remove me from the class view' : 'Include my progress (anonymous)'}</button>
    </div>
  )

  if (d.hidden) return (
    <div className="space-y-5">
      <div><div className="eyebrow">Class view</div><h1 className="h-page">{d.name}</h1></div>
      <div className="card p-6 space-y-2 max-w-3xl">
        <b className="text-navy text-lg">Not enough learners yet</b>
        <p className="text-sm text-muted">{d.n_learners} of {d.min_learners} learners have joined. {d.privacy_note}</p>
        <p className="text-sm text-muted">This view will show where learners as a group stand and which misconceptions are most common. It uses only real learners who chose to be included, and no made-up data.</p>
      </div>
      {joinBox}
    </div>
  )

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div><div className="eyebrow">Class view · anonymous</div><h1 className="h-page">{d.name}</h1>
          <p className="text-muted mt-1 max-w-3xl">Which ideas does the whole class get wrong? A score can't tell you — misconceptions can. {d.n_learners} learners · aggregated, no transcripts.</p></div>
        {d.is_mock && <DemoBadge label="demo class" title="Synthetic cohort generated for the demo. A real cohort uses the same code over real learners." />}
      </div>

      {joinBox}
      <div className="grid lg:grid-cols-[1fr_360px] gap-5">
        <div className="card p-5 min-w-0">
          <SectionTitle eyebrow="Concept heat-map" title="Where the class stands" />
          <div className="space-y-2">
            {d.concepts.map((c: any) => {
              const tot = Object.values(c.levels).reduce((a: number, b: any) => a + b, 0) as number || 1
              return (
                <div key={c.concept_id} className="grid grid-cols-[170px_1fr_44px] items-center gap-3 text-sm">
                  <span className="font-semibold text-navy truncate" title={c.name}>{c.name}</span>
                  <div className="flex h-5 rounded-md overflow-hidden bg-line" role="img" aria-label={Object.entries(c.levels).map(([k, v]) => `${v} ${k}`).join(', ')}>
                    {(['unknown', 'developing', 'proficient', 'mastered'] as const).map(k => c.levels[k] > 0 && <div key={k} title={`${c.levels[k]} ${k}`} style={{ width: `${(c.levels[k] / tot) * 100}%`, background: COL[k] }} />)}
                  </div>
                  <span className="text-xs text-muted text-right">{Math.round(c.avg_p * 100)}%</span>
                </div>
              )
            })}
          </div>
          <div className="flex gap-4 mt-3 text-xs text-muted font-semibold">{Object.entries(COL).map(([k, v]) => <span key={k} className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded" style={{ background: v }} />{k === 'unknown' ? 'needs work' : k}</span>)}</div>
        </div>
        <div className="space-y-4">
          <div className="card p-5"><SectionTitle eyebrow="Most common" title="Class-wide misconceptions" />
            <ul className="space-y-3">{d.top_misconceptions.map((m: any) => (
              <li key={m.misconception_id}><div className="flex justify-between text-sm font-bold text-navy"><span>{m.name}</span><span className="text-violet">{m.count} learners</span></div>
                <div className="text-xs text-muted">{m.concept_name} · {Math.round(m.share * 100)}% of class</div>
                <div className="h-1.5 rounded-full bg-line mt-1"><div className="h-full rounded-full bg-violet" style={{ width: `${m.share * 100}%` }} /></div></li>))}</ul>
            <p className="text-xs text-muted mt-3">Teaching tip: a 10-minute "contrasting cases" demo on the top item usually fixes more than re-teaching the whole unit.</p></div>
          <div className="card p-5"><SectionTitle eyebrow="Needs attention" title="Learners who may need help" />
            <ul className="space-y-2">{d.needs_attention.map((n: any) => <li key={n.ref} className="text-sm"><b className="text-navy">{n.display_name}</b><div className="text-xs text-muted">{n.reason}</div></li>)}{!d.needs_attention.length && <li className="text-sm text-muted">Nobody flagged.</li>}</ul>
            <p className="text-[11px] text-muted mt-3">{d.privacy_note}</p></div>
        </div>
      </div>
    </div>
  )
}
