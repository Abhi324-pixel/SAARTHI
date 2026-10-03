import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { apiT06, type ProgressHistory, type RadarDomain } from '../api_ext/T06'
import RadarChart from '../components/RadarChart'
import TrendChart from '../components/TrendChart'
import { Bar, Callout, FlagChip, LevelChip, SectionTitle, Spinner } from '../components/ui'
import { useApp } from '../store'

const SRC: Record<string, string> = { question: 'Question', work_product: 'Your SQL', explain_back: 'Teach-back', mentor: 'Mentor', self_report: 'You said', feedback: 'Feedback' }

export default function Genome() {
  const { version, toast, bump } = useApp()
  const [g, setG] = useState<any | null>(null)
  const [progress, setProgress] = useState<ProgressHistory | null>(null)
  const [radar, setRadar] = useState<RadarDomain[]>([])

  useEffect(() => {
    api.genome().then(setG).catch(e => toast(e.message, 'err'))
    apiT06.history().then(setProgress).catch(() => {})
    apiT06.radar().then(r => setRadar(r.domains)).catch(() => {})
  }, [version, toast])

  if (!g) return <div className="py-20 flex justify-center"><Spinner label="Loading your Learning Genome…" /></div>

  const lastPoint = progress?.series && progress.series.length > 0
    ? progress.series[progress.series.length - 1]
    : null
  const hasDip = Boolean(
    lastPoint &&
    progress?.now &&
    progress.now.overall < lastPoint.overall - 0.005 &&
    progress.due_reviews > 0
  )

  async function dispute(concept_id: string) {
    try { const r = await api.dispute({ concept_id, kind: 'dispute_level', note: 'learner disagrees' }); toast(r.message); bump() } catch (e: any) { toast(e.message, 'err') }
  }

  return (
    <div className="space-y-6">
      <div className="card p-6 lg:p-8">
        <div className="eyebrow">Learning Genome</div>
        <h1 className="h-page mt-1">What SAARTHI believes about you — and why</h1>
        <p className="text-slate-300 desc-glow mt-2 max-w-3xl leading-relaxed">
          This is the plain-language view of your Learner Twin. Everything here comes from recorded evidence, you can see the evidence, and you can tell SAARTHI when it's wrong. It never labels you with a "learning style" or guesses your feelings from your voice.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-5" id="t06-progress-section">
        <div className="card p-5 lg:p-6 lg:col-span-2">
          <SectionTitle
            eyebrow="Progress over time"
            title="How your twin is growing"
            right={
              progress?.now ? (
                <span className="text-xs text-slate-300 desc-glow font-mono">
                  Current: <b className="text-white">{Math.round(progress.now.overall * 100)}%</b>
                </span>
              ) : undefined
            }
          />
          {hasDip && (
            <div className="mb-4">
              <Callout tone="saffron">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-slate-100">
                    <b>Memory fades without review</b> — {progress?.due_reviews} review{progress?.due_reviews! > 1 ? 's are' : ' is'} due. Complete your reviews to restore your mastery.
                  </span>
                  <Link to="/reviews" className="underline font-semibold text-xs text-[#FF8A24] hover:text-white transition">
                    Do reviews now →
                  </Link>
                </div>
              </Callout>
            </div>
          )}
          <TrendChart
            series={progress?.series ?? []}
            markers={progress?.markers ?? []}
            projection={progress?.projection ?? { overall: 0, weeks: 0 }}
          />
        </div>

        <div className="card p-5 lg:p-6 flex flex-col justify-between">
          <div>
            <SectionTitle eyebrow="Domain radar" title="Current vs. target" />
            <p className="text-xs text-slate-400 desc-glow -mt-1 mb-2">Across key role competencies</p>
          </div>
          <div className="flex-1 flex flex-col justify-center py-2">
            <RadarChart domains={radar} />
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div className="card p-5 lg:p-6">
          <SectionTitle eyebrow="Strengths" title="Concepts you have mastered" />
          {g.strengths.length ? (
            <ul className="space-y-2.5 mt-2">
              {g.strengths.map((s: any) => (
                <li key={s.concept_id} className="glass-row px-3.5 py-2.5 flex items-center gap-2.5">
                  <Link className="font-bold text-white hover:text-[#FF8A24] transition-colors" to={'/learn/' + s.concept_id}>{s.name}</Link>
                  <LevelChip level={s.level} />
                  <span className="text-xs text-slate-400 font-mono ml-auto">{Math.round(s.p * 100)}%</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-slate-400 desc-glow py-3">Nothing proven yet — a few answers will change that.</div>
          )}
        </div>

        <div className="card p-5 lg:p-6">
          <SectionTitle eyebrow="Bottlenecks" title="What's holding you back" />
          {g.bottlenecks.length ? (
            <ul className="space-y-2.5 mt-2">
              {g.bottlenecks.map((s: any) => (
                <li key={s.concept_id} className="glass-row px-3.5 py-2.5 flex items-center gap-2.5 flex-wrap">
                  <Link className="font-bold text-white hover:text-[#FF8A24] transition-colors" to={'/learn/' + s.concept_id}>{s.name}</Link>
                  {s.flags.map((f: string) => <FlagChip key={f} flag={f} />)}
                  <button className="text-xs text-slate-400 underline hover:text-white ml-auto" onClick={() => dispute(s.concept_id)}>I disagree</button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-slate-400 desc-glow py-3">No clear bottleneck yet.</div>
          )}
        </div>
      </div>

      {g.misconceptions.length > 0 && (
        <div className="card p-5 lg:p-6">
          <SectionTitle eyebrow="Misconceptions" title="Active incorrect mental models" />
          <div className="grid md:grid-cols-2 gap-4 mt-2">
            {g.misconceptions.map((m: any) => (
              <div key={m.instance_id} className="card p-4 border-[rgba(168,85,247,0.35)] bg-[rgba(168,85,247,0.08)]">
                <div className="flex items-center justify-between gap-2">
                  <b className="text-[#C084FC] heading-glow">{m.name}</b>
                  <span className="chip" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#C084FC', border: '1px solid rgba(168, 85, 247, 0.35)' }}>{m.status.replace('_', ' ')}</span>
                </div>
                <div className="text-sm text-slate-200 desc-glow mt-1.5">{m.description}</div>
                <div className="text-xs text-slate-400 desc-glow mt-1">Found via {m.channel.replace('_', ' ')} · {m.cycles} correction cycle(s)</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-5">
        <div className="card p-5 lg:p-6">
          <SectionTitle eyebrow="Pedagogy Twin" title="Teaching approaches that work" />
          {g.strategies.length ? (
            <ul className="space-y-3 mt-2">
              {g.strategies.map((s: any) => (
                <li key={s.strategy} className="space-y-1">
                  <div className="flex justify-between text-sm font-semibold">
                    <span className="text-slate-200">{s.label}</span>
                    <span className="text-slate-400 text-xs font-mono">{s.success}/{s.n} improved · avg gain {Math.round(s.mean_gain * 100)} pts</span>
                  </div>
                  <Bar value={s.n ? s.success / s.n : 0} color="#4D9DFF" h={6} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-slate-400 desc-glow py-3">Shown once SAARTHI has seen a few explanations followed by a <i>later</i> result.</div>
          )}
          <div className="text-[11px] text-slate-400 desc-glow mt-3 pt-2 border-t border-[rgba(210,225,235,0.12)]">{g.strategy_note}</div>
        </div>

        <div className="card p-5 lg:p-6">
          <SectionTitle eyebrow="Metacognition" title="Confidence vs. results" />
          {g.calibration.n ? (
            <div className="space-y-2.5 mt-2">
              {(['low', 'mid', 'high'] as const).map(k => {
                const b = g.calibration.bins[k]
                return (
                  <div key={k} className="text-sm space-y-1">
                    <div className="flex justify-between font-semibold">
                      <span className="text-slate-200">{k === 'low' ? 'Unsure' : k === 'mid' ? 'Maybe' : 'Sure'}</span>
                      <span className="text-slate-400 text-xs font-mono">{b.n ? `${b.correct}/${b.n} right` : '—'}</span>
                    </div>
                    <Bar value={b.accuracy ?? 0} color="#4D9DFF" h={6} />
                  </div>
                )
              })}
              {g.calibration.message && <Callout tone="saffron">{g.calibration.message}</Callout>}
            </div>
          ) : (
            <div className="text-sm text-slate-400 desc-glow py-3">Answer a few questions with a confidence rating to unlock your calibration curves.</div>
          )}
        </div>
      </div>

      <div className="card p-5 lg:p-6">
        <SectionTitle eyebrow="Evidence log" title="Every change to your Twin, with its source" right={<span className="text-xs text-slate-400 desc-glow">Only questions, your SQL, teach-backs and mentors move mastery.</span>} />
        <div className="overflow-auto mt-2 rounded-xl border border-[rgba(210,225,235,0.14)] bg-[rgba(16,26,36,0.6)]">
          <table className="w-full text-sm">
            <thead className="bg-[rgba(25,39,51,0.8)] border-b border-[rgba(210,225,235,0.14)]">
              <tr className="text-left text-xs text-slate-300">
                <th className="py-2.5 px-3">When</th>
                <th className="px-3">Concept</th>
                <th className="px-3">Source</th>
                <th className="px-3">Result</th>
                <th className="px-3">Estimate</th>
                <th className="px-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[rgba(210,225,235,0.08)]">
              {g.evidence.map((e: any) => (
                <tr key={e.id} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                  <td className="py-2 px-3 text-xs text-slate-400 whitespace-nowrap font-mono">{e.at.slice(5).replace('T', ' ')}</td>
                  <td className="px-3 font-semibold text-white">{e.concept}</td>
                  <td className="px-3">
                    <span className="chip" style={{ background: 'rgba(210, 225, 235, 0.08)', color: '#AEBBC5' }}>{SRC[e.source] ?? e.source}</span>
                  </td>
                  <td className="px-3">
                    {e.score === null ? '—' : e.score >= 0.6 ? <span className="text-[#35D07F] font-bold">✓</span> : <span className="text-[#FF5364] font-bold">✗</span>}
                    {e.confidence ? <span className="text-xs text-slate-400"> · sure {e.confidence}/5</span> : null}
                  </td>
                  <td className="px-3 whitespace-nowrap font-mono text-xs">
                    {e.moved ? `${Math.round((e.p_before ?? 0) * 100)}% → ${Math.round((e.p_after ?? 0) * 100)}%` : <span className="text-slate-500">recorded, no change</span>}
                  </td>
                  <td className="px-3">
                    <button className="text-xs underline text-slate-400 hover:text-white" onClick={() => dispute(e.concept_id)}>dispute</button>
                  </td>
                </tr>
              ))}
              {!g.evidence.length && <tr><td colSpan={6} className="py-5 text-slate-400 text-center desc-glow">No evidence logged yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {g.corrections.length > 0 && (
        <div className="card p-5 lg:p-6">
          <SectionTitle eyebrow="Your corrections" title="Things you've told SAARTHI are wrong" />
          <div className="space-y-1.5 mt-2">
            {g.corrections.map((c: any) => (
              <div key={c.id} className="glass-row px-3.5 py-2 text-sm flex items-center justify-between">
                <span className="text-slate-200">{c.concept_id.replace(/_/g, ' ')} — {c.kind.replace('_', ' ')}</span>
                <span className="chip" style={{ background: 'rgba(210, 225, 235, 0.08)', color: '#AEBBC5' }}>{c.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
