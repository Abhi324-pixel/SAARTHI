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

  if (!g) return <div className="py-16 flex justify-center"><Spinner /></div>

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
    <div className="space-y-5">
      <div><div className="eyebrow">Learning Genome</div><h1 className="h-page">What SAARTHI believes about you — and why</h1>
        <p className="text-muted mt-1 max-w-3xl">This is the plain-language view of your Learner Twin. Everything here comes from recorded evidence, you can see the evidence, and you can tell SAARTHI when it's wrong. It never labels you with a "learning style" or guesses your feelings from your voice.</p></div>

      <div className="grid lg:grid-cols-3 gap-4" id="t06-progress-section">
        <div className="card p-5 lg:col-span-2">
          <SectionTitle
            eyebrow="Progress over time"
            title="How your twin is growing"
            right={
              progress?.now ? (
                <span className="text-xs text-muted">
                  Current: <b>{Math.round(progress.now.overall * 100)}%</b>
                </span>
              ) : undefined
            }
          />
          {hasDip && (
            <div className="mb-4">
              <Callout tone="saffron">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span>
                    <b>Memory fades without review</b> — {progress?.due_reviews} review{progress?.due_reviews! > 1 ? 's are' : ' is'} due. Complete your reviews to restore your mastery.
                  </span>
                  <Link to="/reviews" className="underline font-semibold text-xs text-navy hover:text-saffron transition">
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

        <div className="card p-5 flex flex-col justify-between">
          <div>
            <SectionTitle eyebrow="Domain radar" title="Current vs. target" />
            <p className="text-xs text-muted -mt-1 mb-2">Across key role competencies</p>
          </div>
          <div className="flex-1 flex flex-col justify-center py-2">
            <RadarChart domains={radar} />
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card p-5"><SectionTitle eyebrow="Strengths" title="You're solid on" />
          {g.strengths.length ? <ul className="space-y-2">{g.strengths.map((s: any) => <li key={s.concept_id} className="flex items-center gap-2"><Link className="font-bold text-navy hover:underline" to={'/learn/' + s.concept_id}>{s.name}</Link><LevelChip level={s.level} /><span className="text-xs text-muted ml-auto">{Math.round(s.p * 100)}%</span></li>)}</ul> : <div className="text-sm text-muted">Nothing proven yet — a few answers will change that.</div>}</div>
        <div className="card p-5"><SectionTitle eyebrow="Bottlenecks" title="What's holding you back" />
          {g.bottlenecks.length ? <ul className="space-y-2">{g.bottlenecks.map((s: any) => <li key={s.concept_id} className="flex items-center gap-2 flex-wrap"><Link className="font-bold text-navy hover:underline" to={'/learn/' + s.concept_id}>{s.name}</Link>{s.flags.map((f: string) => <FlagChip key={f} flag={f} />)}<button className="text-xs text-muted underline ml-auto" onClick={() => dispute(s.concept_id)}>I disagree</button></li>)}</ul> : <div className="text-sm text-muted">No clear bottleneck yet.</div>}</div>
      </div>

      {g.misconceptions.length > 0 && (
        <div className="card p-5"><SectionTitle eyebrow="Misconceptions" title="Incorrect mental models found" />
          <div className="grid md:grid-cols-2 gap-3">{g.misconceptions.map((m: any) => (
            <div key={m.instance_id} className="rounded-xl border border-[#d9b8e6] bg-[#fbf6fd] p-3"><b className="text-violet">{m.name}</b> <span className="chip" style={{ background: '#fff', color: '#7b1fa2', border: '1px solid #d9b8e6' }}>{m.status.replace('_', ' ')}</span>
              <div className="text-sm mt-1">{m.description}</div><div className="text-xs text-muted mt-1">Found via {m.channel.replace('_', ' ')} · {m.cycles} correction cycle(s)</div></div>))}</div></div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card p-5"><SectionTitle eyebrow="What works for you" title="Teaching approaches" />
          {g.strategies.length ? <ul className="space-y-2.5">{g.strategies.map((s: any) => <li key={s.strategy}><div className="flex justify-between text-sm font-semibold"><span>{s.label}</span><span className="text-muted text-xs">{s.success}/{s.n} improved · avg gain {Math.round(s.mean_gain * 100)} pts</span></div><Bar value={s.n ? s.success / s.n : 0} color="#1f7a7a" h={6} /></li>)}</ul> : <div className="text-sm text-muted">Shown once SAARTHI has seen a few explanations followed by a <i>later</i> result.</div>}
          <div className="text-[11px] text-muted mt-3">{g.strategy_note}</div></div>
        <div className="card p-5"><SectionTitle eyebrow="Self-awareness" title="Confidence vs. results" />
          {g.calibration.n ? <div className="space-y-2">{(['low', 'mid', 'high'] as const).map(k => { const b = g.calibration.bins[k]; return <div key={k} className="text-sm"><div className="flex justify-between font-semibold"><span>{k === 'low' ? 'Unsure' : k === 'mid' ? 'Maybe' : 'Sure'}</span><span className="text-muted text-xs">{b.n ? `${b.correct}/${b.n} right` : '—'}</span></div><Bar value={b.accuracy ?? 0} color="#1f7a7a" h={6} /></div> })}{g.calibration.message && <Callout tone="saffron">{g.calibration.message}</Callout>}</div> : <div className="text-sm text-muted">Answer a few questions with a confidence rating.</div>}</div>
      </div>

      <div className="card p-5">
        <SectionTitle eyebrow="Evidence log" title="Every change to your Twin, with its source" right={<span className="text-xs text-muted">Only questions, your SQL, teach-backs and mentors move mastery.</span>} />
        <div className="overflow-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="py-1.5 pr-3">When</th><th className="pr-3">Concept</th><th className="pr-3">Source</th><th className="pr-3">Result</th><th className="pr-3">Estimate</th><th /></tr></thead>
          <tbody>{g.evidence.map((e: any) => (
            <tr key={e.id} className="border-t border-line"><td className="py-1.5 pr-3 text-xs text-muted whitespace-nowrap">{e.at.slice(5).replace('T', ' ')}</td><td className="pr-3 font-semibold">{e.concept}</td>
              <td className="pr-3"><span className="chip" style={{ background: '#e8eef5', color: '#16324f' }}>{SRC[e.source] ?? e.source}</span></td>
              <td className="pr-3">{e.score === null ? '—' : e.score >= 0.6 ? <span className="text-lvl-proficient font-bold">✓</span> : <span className="text-lvl-unknown font-bold">✗</span>}{e.confidence ? <span className="text-xs text-muted"> · sure {e.confidence}/5</span> : null}</td>
              <td className="pr-3 whitespace-nowrap">{e.moved ? `${Math.round((e.p_before ?? 0) * 100)}% → ${Math.round((e.p_after ?? 0) * 100)}%` : <span className="text-muted text-xs">recorded, no change</span>}</td>
              <td><button className="text-xs underline text-muted" onClick={() => dispute(e.concept_id)}>dispute</button></td></tr>))}
            {!g.evidence.length && <tr><td colSpan={6} className="py-4 text-muted text-center">No evidence yet.</td></tr>}</tbody></table></div>
      </div>
      {g.corrections.length > 0 && <div className="card p-5"><SectionTitle eyebrow="Your corrections" title="Things you've told SAARTHI are wrong" />{g.corrections.map((c: any) => <div key={c.id} className="text-sm py-1">{c.concept_id.replace(/_/g, ' ')} — {c.kind.replace('_', ' ')} <span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{c.status}</span></div>)}</div>}
    </div>
  )
}
