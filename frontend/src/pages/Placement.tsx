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
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="card p-6 lg:p-7">
        <div className="eyebrow">Placement Evaluation</div>
        <h1 className="h-page mt-1">Discover what you already know</h1>
        <p className="text-slate-300 desc-glow mt-2 leading-relaxed">
          SAARTHI selects each question adaptively based on your previous answers — prioritizing areas vital to your career goal where estimation uncertainty is highest. Wrong answers pinpoint specific misconceptions.
        </p>
      </div>

      {!done && <QuizRunner key={round} total={8} title="Placement question" onFinish={s => { setDone(s); bump() }} />}

      {done && (
        <div className="card p-6 lg:p-8 space-y-4.5 pop">
          <h2 className="text-2xl font-extrabold text-white heading-glow">
            Placement complete — <span className="text-[#35D07F]">{done.correct}</span> of {done.total} correct
          </h2>
          {done.misconceptions.length > 0 && (
            <Callout tone="violet" title="Possible misconceptions spotted">
              {[...new Set<string>(done.misconceptions)].join(' · ')}. SAARTHI will cross-check these with your own SQL exercises before confirming them.
            </Callout>
          )}
          {done.changes.length > 0 && (
            <Callout tone="navy" title="Your roadmap was rebuilt dynamically as you answered" icon="↻">
              {done.changes[done.changes.length - 1]}
            </Callout>
          )}
          <div className="flex flex-wrap gap-3 pt-2">
            <Link to="/" className="btn btn-primary">Go to my dashboard</Link>
            <Link to="/roadmap" className="btn btn-ghost">See my roadmap & why</Link>
            <button className="btn btn-ghost" onClick={() => { setDone(null); setRound(r => r + 1) }}>8 more questions</button>
          </div>
        </div>
      )}
    </div>
  )
}
