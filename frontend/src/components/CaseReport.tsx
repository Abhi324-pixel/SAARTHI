import { Callout, FlagChip, LevelChip } from './ui'

/** The case report exactly as a mentor sees it (first name and age group only; nothing else about the learner). */
export default function CaseReport({ report }: { report: any }) {
  const r = report ?? {}
  return (
    <div className="space-y-3 text-sm">
      {r.concept && <div className="rounded-xl bg-paper p-3"><b>{r.concept.name}</b> · <LevelChip level={r.concept.level} /> {Math.round(r.concept.p * 100)}% {r.concept.flags?.map((f: string) => <FlagChip key={f} flag={f} />)}</div>}
      <Row k="Learner" v={r.learner ? `${r.learner.first_name} · ${r.learner.age_band === 'under_18' ? 'under 18 — extra care' : 'adult'}` : undefined} />
      <Row k="Goal" v={r.learner?.goal} /><Row k="Language" v={r.learner?.language} /><Row k="Why now" v={r.reason} /><Row k="Their note" v={r.learner_note} />
      {r.misconceptions?.length > 0 && <div><div className="text-xs font-bold text-muted">Misconceptions</div>{r.misconceptions.map((m: any, i: number) => <div key={i}><FlagChip flag="misconception" /> {m.name} <span className="text-muted text-xs">({m.status}, {m.cycles} cycles)</span>{m.learner_statement && <div className="text-xs italic text-muted">“{m.learner_statement}”</div>}</div>)}</div>}
      {r.strategies_tried?.length > 0 && <div><div className="text-xs font-bold text-muted">Already tried</div><div className="flex flex-wrap gap-1 mt-1">{r.strategies_tried.map((s: any, i: number) => <span key={i} className="chip" style={{ background: '#eceff3', color: '#16324f' }}>{s.strategy.replace('_', ' ')}{s.gain !== null && s.gain !== undefined ? ` (${s.gain >= 0 ? '+' : ''}${Math.round(s.gain * 100)})` : ''}</span>)}</div></div>}
      {r.evidence_timeline?.length > 0 && <div><div className="text-xs font-bold text-muted">Recent evidence</div><ul className="text-xs mt-1 space-y-0.5">{r.evidence_timeline.map((e: any, i: number) => <li key={i}>{e.at.slice(5).replace('T', ' ')} · {e.source.replace('_', ' ')} · {e.correct === null ? '—' : e.correct ? '✓' : '✗'}</li>)}</ul></div>}
      {r.prerequisite_state?.length > 0 && <div><div className="text-xs font-bold text-muted">Prerequisites</div><div className="text-xs">{r.prerequisite_state.map((p: any) => `${p.concept}: ${p.level}`).join(' · ')}</div></div>}
      {r.suggested_intervention?.length > 0 && <Callout tone="teal" title="Suggested intervention">{r.suggested_intervention[0]}</Callout>}
      {r.transcript_excerpts && <div><div className="text-xs font-bold text-muted">Conversation excerpts the learner chose to share</div>{r.transcript_excerpts.map((t: any, i: number) => <div key={i} className="text-xs"><b>{t.role}:</b> {t.text}</div>)}</div>}
    </div>
  )
}

function Row({ k, v }: { k: string; v?: string }) { return v ? <div><span className="text-xs font-bold text-muted block">{k}</span>{v}</div> : null }
