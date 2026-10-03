import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import QuizRunner from '../components/QuizRunner'
import { Callout, Spinner } from '../components/ui'
import { useApp } from '../store'

export default function Reviews() {
  const { version } = useApp()
  const [d, setD] = useState<any | null>(null)
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)
  useEffect(() => { api.reviewsDue().then(setD) }, [version])
  if (!d) return <div className="py-16 flex justify-center"><Spinner /></div>
  const total = d.items.length
  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div><div className="eyebrow">Spaced review</div><h1 className="h-page">Keep it fresh</h1>
        <p className="text-muted mt-1">Things you learned fade unless you retrieve them. Each concept resurfaces after a growing gap (1, 3, 7, 14, 30 days). A miss lowers your estimate and may re-open the concept.</p></div>
      {total === 0 && !done && <div className="card p-6 text-sm">Nothing is due right now. 🎉 <Link className="underline font-bold text-teal" to="/">Back to dashboard</Link><div className="text-xs text-muted mt-2">Demo tip: Settings → Demo tools → "Advance time" makes reviews fall due.</div></div>}
      {total > 0 && !running && !done && (
        <div className="card p-6 space-y-3"><div className="font-extrabold text-navy">{total} review question(s) due</div>
          <ul className="text-sm list-disc pl-5">{d.due.map((x: any) => <li key={x.concept_id}>{x.name} <span className="text-muted">(now {Math.round(x.p * 100)}%)</span></li>)}</ul>
          <button className="btn btn-saffron" onClick={() => setRunning(true)}>Start review</button></div>
      )}
      {running && !done && <QuizRunner total={total} fixedItems={d.items.map((i: any) => ({ ...i.item, concept_name: i.concept_name }))} title="Review" onFinish={() => { setRunning(false); setDone(true) }} />}
      {done && <Callout tone="teal" title="Review complete">Your estimates are updated and the next reviews are scheduled further out for the ones you remembered. <Link className="underline font-bold" to="/roadmap">See the roadmap</Link></Callout>}
    </div>
  )
}
