import { useEffect, useState } from 'react'
import { api } from '../api'
import { useApp } from '../store'
import { Bar, Callout, ConfidencePicker, FlagChip, LevelChip, Spinner } from './ui'

/** Adaptive question runner with confidence rating. Used for placement, concept checks and spaced reviews. */
export default function QuizRunner({ total, conceptId, title, onFinish, fixedItems }: {
  total: number; conceptId?: string; title?: string; onFinish?: (summary: any) => void; fixedItems?: any[]
}) {
  const { toast, bump, setRoadmapNote } = useApp()
  const [n, setN] = useState(0)
  const [item, setItem] = useState<any | null>(null)
  const [pick, setPick] = useState<number | null>(null)
  const [conf, setConf] = useState<number | null>(null)
  const [res, setRes] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [stats, setStats] = useState({ correct: 0, misconceptions: [] as string[], changes: [] as string[] })
  const [finished, setFinished] = useState(false)

  async function load(i: number) {
    setLoading(true); setPick(null); setConf(null); setRes(null)
    try {
      if (fixedItems) { setItem(fixedItems[i] ?? null) }
      else {
        const out = await api.probeNext(1, conceptId)
        setItem(out.items[0] ?? null)
      }
    } catch (e: any) { toast(e.message, 'err') } finally { setLoading(false) }
  }
  useEffect(() => { load(0) /* eslint-disable-next-line */ }, [conceptId])

  async function submit() {
    if (pick === null || !item) return
    setBusy(true)
    try {
      const r = await api.probeAnswer({ item_id: item.id, option_index: pick, stated_confidence: conf })
      setRes(r)
      setStats(s => ({
        correct: s.correct + (r.correct ? 1 : 0),
        misconceptions: r.misconception ? [...s.misconceptions, r.misconception.name] : s.misconceptions,
        changes: r.after?.roadmap?.changed ? [...s.changes, r.after.roadmap.change_reason] : s.changes,
      }))
      if (r.after?.roadmap?.changed) setRoadmapNote(r.after.roadmap.change_reason)
      bump()
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  async function next() {
    const i = n + 1
    if (i >= total || (!fixedItems && false)) {
      setFinished(true); onFinish?.({ ...stats, total }); return
    }
    setN(i); await load(i)
  }

  if (finished) return null
  if (loading) return <div className="card p-6"><Spinner label="Choosing your next question…" /></div>
  if (!item) return <div className="card p-6 text-sm text-muted">No more questions available for this topic right now. You've seen them all — nice work.<div className="mt-3"><button className="btn btn-primary" onClick={() => { setFinished(true); onFinish?.({ ...stats, total: n }) }}>Finish</button></div></div>

  return (
    <div className="card p-5 pop" aria-live="polite">
      <div className="flex items-center justify-between mb-2">
        <div className="eyebrow">{title ?? 'Question'} {n + 1} of {total}</div>
        <span className="text-xs font-semibold text-muted">{item.concept_name}</span>
      </div>
      <Bar value={(n + (res ? 1 : 0)) / total} h={6} />
      <pre className="mt-4 whitespace-pre-wrap font-sans font-bold text-navy text-[1.02rem] leading-relaxed">{item.stem}</pre>
      <div className="mt-3 grid gap-2" role="radiogroup" aria-label="Answer options">
        {item.options.map((o: any) => {
          const chosen = pick === o.index
          const isCorrect = res && o.text === res.correct_option
          const isWrongChosen = res && chosen && !res.correct
          return (
            <button key={o.index} role="radio" aria-checked={chosen} disabled={!!res} onClick={() => setPick(o.index)}
              className={`text-left rounded-xl border px-4 py-3 text-sm font-medium transition ${isCorrect ? 'border-lvl-proficient bg-[#e8f6ee]' : isWrongChosen ? 'border-lvl-unknown bg-[#fdeaea]' : chosen ? 'border-saffron bg-saffron-soft ring-2 ring-saffron/30' : 'border-line bg-white hover:bg-paper'}`}>
              <span className="font-mono">{o.text}</span>
              {isCorrect && <span className="ml-2 text-lvl-proficient font-bold">✓</span>}
              {isWrongChosen && <span className="ml-2 text-lvl-unknown font-bold">✗</span>}
            </button>
          )
        })}
      </div>
      {!res && (
        <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
          <ConfidencePicker value={conf} onChange={setConf} />
          <button className="btn btn-saffron" disabled={pick === null || busy} onClick={submit}>{busy ? 'Checking…' : 'Check answer'}</button>
        </div>
      )}
      {res && (
        <div className="mt-4 space-y-2.5">
          <Callout tone={res.correct ? 'teal' : 'red'} title={res.correct ? 'Correct' : 'Not quite'}>
            {res.explanation}
            <div className="mt-1.5 flex items-center gap-2 flex-wrap text-xs">
              <span>{res.concept_name}: {Math.round(res.mastery.p_before * 100)}% → <b>{Math.round(res.mastery.p_after * 100)}%</b></span>
              <LevelChip level={res.mastery.level_after} />
            </div>
          </Callout>
          {res.calibration && <Callout tone="saffron" title="Confidence check">{res.calibration}</Callout>}
          {res.misconception && (
            <Callout tone="violet" title={`Possible misconception: ${res.misconception.name}`}>
              <FlagChip flag="misconception" /> <span className="ml-1">{res.misconception.status === 'candidate' ? 'Noted — one more signal and it becomes a confirmed flag. You can dispute it any time.' : 'Confirmed by repeated evidence. Your roadmap now includes a targeted fix.'}</span>
            </Callout>
          )}
          {res.after?.roadmap?.changed && <Callout tone="navy" title="Roadmap updated" icon="↻">{res.after.roadmap.change_reason}</Callout>}
          <div className="flex justify-end"><button className="btn btn-primary" onClick={next}>{n + 1 >= total ? 'Finish' : 'Next question →'}</button></div>
        </div>
      )}
    </div>
  )
}
