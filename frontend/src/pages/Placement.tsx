import { useState } from 'react'
import { Link } from 'react-router-dom'
import QuizRunner from '../components/QuizRunner'
import { Callout } from '../components/ui'
import { useApp } from '../store'

export default function Placement() {
  const { bump } = useApp()
  const [done, setDone] = useState<any | null>(null)
  const [round, setRound] = useState(0)

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div><div className="eyebrow">Placement</div><h1 className="h-page">Find out what you really know</h1>
        <p className="text-muted mt-1">SAARTHI picks each question based on your previous answers — where your goal matters most and the estimate is shakiest. Wrong answers are useful: each wrong option is tied to a specific misconception.</p></div>
      {!done && <QuizRunner key={round} total={8} title="Placement question" onFinish={s => { setDone(s); bump() }} />}
      {done && (
        <div className="card p-6 space-y-4 pop">
          <h2 className="text-xl font-extrabold text-navy">Placement complete — {done.correct} of {done.total} correct</h2>
          {done.misconceptions.length > 0 && <Callout tone="violet" title="Possible misconceptions spotted">{[...new Set<string>(done.misconceptions)].join(' · ')}. SAARTHI will check these with your own SQL before calling them confirmed.</Callout>}
          {done.changes.length > 0 && <Callout tone="navy" title="Your roadmap was rebuilt as you answered" icon="↻">{done.changes[done.changes.length - 1]}</Callout>}
          <div className="flex flex-wrap gap-2">
            <Link to="/" className="btn btn-primary">Go to my dashboard</Link>
            <Link to="/roadmap" className="btn btn-saffron">See my roadmap & why</Link>
            <button className="btn btn-ghost" onClick={() => { setDone(null); setRound(r => r + 1) }}>8 more questions</button>
          </div>
        </div>
      )}
    </div>
  )
}
