import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import QuizRunner from '../components/QuizRunner'
import { Callout, Spinner } from '../components/ui'
import { useApp } from '../store'
import { RotateCcw, Clock, CheckCircle2, Sparkles, ArrowRight, BookOpen } from 'lucide-react'

export default function Reviews() {
  const { version } = useApp()
  const [d, setD] = useState<any | null>(null)
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    api.reviewsDue().then(setD)
  }, [version])

  if (!d) return (
    <div className="py-24 flex flex-col items-center justify-center gap-3">
      <Spinner label="Checking spaced repetition queue…" />
    </div>
  )

  const total = d.items.length

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="glass-panel p-6 sm:p-8 space-y-2">
        <div className="eyebrow flex items-center gap-1.5">
          <RotateCcw className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
          Spaced Repetition
        </div>
        <h1 className="h-page heading-glow">Keep Your Foundations Fresh</h1>
        <p className="desc-glow text-[var(--text-secondary)] text-sm sm:text-base leading-relaxed">
          Knowledge naturally decays over time without active retrieval. Each mastered concept resurfaces along an exponential interval schedule (1, 3, 7, 14, 30 days). A miss lowers your certainty and prompts targeted reinforcement.
        </p>
      </div>

      {total === 0 && !done && (
        <div className="card p-8 text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-[rgba(53,208,127,0.12)] border border-[rgba(53,208,127,0.3)] flex items-center justify-center text-[#35D07F] mx-auto shadow-[0_0_20px_rgba(53,208,127,0.2)]">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[var(--text-primary)]">All Caught Up!</h2>
            <p className="desc-glow text-sm text-[var(--text-secondary)] mt-1 max-w-md mx-auto">
              No concepts are due for review right now. Your retention curves are healthy.
            </p>
          </div>
          <div className="flex justify-center gap-3 pt-2">
            <Link className="btn btn-secondary flex items-center gap-2" to="/">
              Back to Dashboard
            </Link>
          </div>
          <div className="text-xs text-[var(--text-muted)] font-mono pt-4 border-t border-[var(--border-subtle)] max-w-sm mx-auto">
            Demo tip: Settings → Demo tools → "Advance time" to simulate future review cycles.
          </div>
        </div>
      )}

      {total > 0 && !running && !done && (
        <div className="card p-6 sm:p-8 space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <div className="text-xl font-extrabold text-[var(--text-primary)] heading-glow flex items-center gap-2">
                <Clock className="w-5 h-5 text-[var(--accent-orange)]" />
                {total} Review Question{total > 1 ? 's' : ''} Due
              </div>
              <div className="text-xs sm:text-sm text-[var(--text-muted)] desc-glow mt-1">
                Active recall tests across previously mastered topics
              </div>
            </div>
            <span className="chip" style={{ background: 'rgba(255, 138, 36, 0.15)', color: 'var(--accent-orange)', border: '1px solid rgba(255, 138, 36, 0.3)' }}>
              Ready for Review
            </span>
          </div>

          <div className="rounded-xl border border-[var(--border-subtle)] bg-[rgba(15,25,35,0.30)] divide-y divide-[var(--border-subtle)] overflow-hidden">
            {d.due.map((x: any) => (
              <div key={x.concept_id} className="p-3.5 flex items-center justify-between gap-3 text-sm">
                <div className="flex items-center gap-2.5 font-medium text-[var(--text-primary)]">
                  <BookOpen className="w-4 h-4 text-[#4D9DFF]" />
                  <span>{x.name}</span>
                </div>
                <div className="text-xs font-mono text-[var(--text-muted)]">
                  Est. retention: <b className="text-[var(--text-primary)]">{Math.round(x.p * 100)}%</b>
                </div>
              </div>
            ))}
          </div>

          <button className="btn btn-orange py-3 px-8 text-sm font-semibold flex items-center gap-2 shadow-[0_6px_20px_rgba(255,120,30,0.25)]" onClick={() => setRunning(true)}>
            <Sparkles className="w-4 h-4" />
            Start Review Session
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {running && !done && (
        <QuizRunner
          total={total}
          fixedItems={d.items.map((i: any) => ({ ...i.item, concept_name: i.concept_name }))}
          title="Spaced Repetition"
          onFinish={() => {
            setRunning(false)
            setDone(true)
          }}
        />
      )}

      {done && (
        <div className="space-y-4">
          <Callout tone="teal" title="Review Completed">
            Your mastery estimates have been updated and spaced retention intervals extended for all remembered concepts.
            <div className="mt-2">
              <Link className="underline font-bold text-[#4D9DFF]" to="/roadmap">
                Inspect updated roadmap schedule →
              </Link>
            </div>
          </Callout>
          <div className="flex gap-3">
            <Link className="btn btn-secondary flex items-center gap-2" to="/">
              Return to Dashboard
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

