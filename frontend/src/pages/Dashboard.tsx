import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import SkillGraph from '../components/SkillGraph'
import StreakCard from '../components/StreakCard'
import { Sparkline } from '../components/TrendChart'
import { Bar, Callout, DemoBadge, FlagChip, LevelChip, Ring, SectionTitle, Spinner } from '../components/ui'
import { useApp } from '../store'

export default function Dashboard() {
  const { me, version, t, toast, bump } = useApp()
  const nav = useNavigate()
  const [d, setD] = useState<any | null>(null)
  const [sel, setSel] = useState<string | null>(null)

  useEffect(() => { api.dashboard().then(setD).catch(e => toast(e.message, 'err')) }, [version, toast])
  if (!d) return <div className="py-16 flex justify-center"><Spinner label="Reading your Learner Twin…" /></div>

  const nodeById = Object.fromEntries(d.graph.nodes.map((n: any) => [n.id, n]))
  const selNode = sel ? nodeById[sel] : null
  const mis = d.misconceptions.filter((m: any) => ['confirmed', 'correcting', 'pending_verify'].includes(m.status))
  const cand = d.misconceptions.filter((m: any) => m.status === 'candidate')
  const missionIcon: Record<string, string> = { fix_misconception: '🛠', review: '🔁', learn: '📘' }

  async function askMentor(s: any) {
    try { const c = await api.createCase({ category: s.category, concept_id: s.concept_id, reason: s.reason, trigger: s.trigger }); toast('Case opened with a full report.'); nav('/mentors/' + c.case_id) }
    catch (e: any) { toast(e.message, 'err') }
  }

  return (
    <div className="space-y-6">
      <div className="grid lg:grid-cols-[1fr_auto] gap-4 items-center">
        <div>
          <div className="eyebrow">{d.role.title} · {me?.weekly_hours}h/week</div>
          <h1 className="h-page">{me?.language === 'english' ? `Welcome back, ${me?.name?.split(' ')[0]}` : `Namaste, ${me?.name?.split(' ')[0]} 🙏`}</h1>
          <p className="text-muted mt-1">{d.has_evidence ? 'Your Learner Twin is updating from everything you do — answers, SQL, and what you say.' : 'Start with the placement so SAARTHI can learn where you really are.'}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Link to="/placement" className="btn btn-primary">Take a quick check</Link>
          <Link to="/practice" className="btn btn-ghost">Practise SQL</Link>
          <button className="btn btn-saffron" onClick={() => nav('/learn/' + (mis[0]?.concept_id ?? d.mission[0]?.concept_id ?? 'sql_outer_join') + '#teachback')}>{t('teachback')}</button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card p-5 flex flex-col justify-between">
          <div className="flex items-center gap-5">
            <Ring value={d.overall} size={112} sub="to goal" />
            <div className="min-w-0">
              <div className="text-xs font-bold text-muted">Overall progress to {d.role.title}</div>
              <div className="text-sm mt-1.5 space-y-1">
                {(['mastered', 'proficient', 'developing', 'unknown'] as const).map(k => (
                  <div key={k} className="flex items-center gap-2"><LevelChip level={k} /> <b>{d.levels[k]}</b></div>
                ))}
                <div className="text-xs text-muted">{d.levels.not_assessed} not assessed yet</div>
              </div>
            </div>
          </div>
          {d.sparkline && d.sparkline.length > 0 && (
            <div className="mt-3 pt-3 border-t border-line flex items-center justify-between gap-2" id="t06-dashboard-sparkline">
              <span className="text-[11px] text-muted font-medium">14-day trend</span>
              <Sparkline points={d.sparkline} width={110} height={20} />
            </div>
          )}
        </div>

        <div className="card p-5 lg:col-span-2">
          <SectionTitle eyebrow="Do this next" title={t('mission')} right={d.due_reviews > 0 ? <Link to="/reviews" className="chip" style={{ background: '#d9f1f5', color: '#0b5d6b' }}>{d.due_reviews} review(s) due →</Link> : undefined} />
          <div className="space-y-2">
            {d.mission.map((m: any, i: number) => (
              <button key={i} onClick={() => nav(m.type === 'review' ? '/reviews' : '/learn/' + m.concept_id)} className="w-full text-left rounded-xl border border-line hover:bg-paper px-4 py-3 flex items-center gap-3 transition">
                <span className="text-xl" aria-hidden>{missionIcon[m.type] ?? '📘'}</span>
                <span className="flex-1 min-w-0"><span className="font-bold text-navy block truncate">{m.title}</span><span className="text-xs text-muted block truncate">{m.reason}</span></span>
                <span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{m.minutes} min</span>
              </button>
            ))}
            {!d.mission.length && <div className="text-sm text-muted">You're all caught up. Try a mock interview or a teach-back to deepen what you know.</div>}
          </div>
        </div>
      </div>

      {(mis.length > 0 || cand.length > 0 || d.escalation_suggestions.length > 0) && (
        <div className="grid md:grid-cols-2 gap-4">
          {mis.map((m: any) => (
            <div key={m.instance_id} className="card p-5" style={{ borderColor: '#d9b8e6', background: '#fbf6fd' }}>
              <div className="flex items-center gap-2 flex-wrap"><FlagChip flag="misconception" /><span className="chip" style={{ background: '#fff', color: '#7b1fa2', border: '1px solid #d9b8e6' }}>{m.status.replace('_', ' ')}</span></div>
              <div className="font-extrabold text-violet mt-2">{m.name}</div>
              <div className="text-sm mt-1">{m.description}</div>
              <div className="text-xs text-muted mt-1">in {m.concept_name} · {m.cycles} correction cycle(s) so far</div>
              <div className="flex gap-2 mt-3 flex-wrap">
                <Link to={'/learn/' + m.concept_id} className="btn btn-primary btn-sm">Fix it now</Link>
                <button className="btn btn-ghost btn-sm" onClick={async () => { try { await api.disputeMis(m.instance_id); toast('Removed — thanks for correcting me.'); bump() } catch (e: any) { toast(e.message, 'err') } }}>This isn't right</button>
              </div>
            </div>
          ))}
          {cand.map((m: any) => (
            <div key={m.instance_id} className="card p-5">
              <div className="chip" style={{ background: '#f3e5f9', color: '#7b1fa2' }}>Possible — needs confirmation</div>
              <div className="font-bold text-navy mt-2">{m.name}</div>
              {m.statement && <div className="text-sm mt-1">You said: “{m.statement}”</div>}
              <div className="flex gap-2 mt-3"><button className="btn btn-primary btn-sm" onClick={async () => { await api.confirmMis(m.instance_id, true); bump() }}>Yes, that's what I think</button><button className="btn btn-ghost btn-sm" onClick={async () => { await api.confirmMis(m.instance_id, false); bump() }}>No</button></div>
            </div>
          ))}
          {d.escalation_suggestions.map((s: any, i: number) => (
            <Callout key={i} tone="navy" title="A human mentor could help here" icon="🤝">
              {s.reason}
              <div className="mt-2"><button className="btn btn-primary btn-sm" onClick={() => askMentor(s)}>Open a mentor case (with full report)</button></div>
            </Callout>
          ))}
        </div>
      )}

      <div className="grid xl:grid-cols-[1fr_340px] gap-4">
        <div className="card p-5 min-w-0">
          <SectionTitle eyebrow="Skill graph" title="What you know, what's blocking you" right={<span className="text-xs text-muted">Click a concept to open it</span>} />
          <SkillGraph nodes={d.graph.nodes} edges={d.graph.edges} onSelect={id => setSel(id)} highlight={sel} />
          {selNode && (
            <div className="mt-3 rounded-xl bg-paper p-3 flex items-center gap-3 flex-wrap pop">
              <b className="text-navy">{selNode.name}</b><LevelChip level={selNode.level} />
              {selNode.flags.map((f: string) => <FlagChip key={f} flag={f} />)}
              <span className="text-xs text-muted">{Math.round(selNode.p * 100)}%{selNode.target ? ` of ${Math.round(selNode.target * 100)}% target` : ''}</span>
              <Link to={'/learn/' + selNode.id} className="btn btn-primary btn-sm ml-auto">Open</Link>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="card p-5">
            <SectionTitle eyebrow="Roadmap" title={`v${d.roadmap.version} · ${d.roadmap.summary.total_weeks} weeks`} right={<Link to="/roadmap" className="text-sm font-bold text-teal">All →</Link>} />
            {d.roadmap.change_reason && <div className="text-xs bg-saffron-soft rounded-lg p-2 mb-3 text-ink/80"><b className="text-saffron">Latest change:</b> {d.roadmap.change_reason}</div>}
            <ol className="space-y-2">
              {d.roadmap.next.map((i: any) => (
                <li key={i.item_id} className="text-sm">
                  <div className="flex items-center gap-2"><span className="h-5 w-5 rounded-full bg-navy text-white text-[11px] font-bold flex items-center justify-center shrink-0">{i.order}</span>
                    <Link to={'/learn/' + i.concept_id} className="font-bold text-navy hover:underline truncate">{i.title}</Link>
                    {i.kind === 'fix_misconception' && <FlagChip flag="misconception" />}
                  </div>
                  <div className="text-xs text-muted ml-7">week {i.week} · {i.minutes} min</div>
                </li>
              ))}
            </ol>
            <div className="mt-3 text-xs text-muted">Readiness now <b className="text-navy">{Math.round(d.roadmap.summary.readiness_now * 100)}%</b> → after plan <b className="text-navy">{Math.round(d.roadmap.summary.readiness_after * 100)}%</b></div>
            <Bar value={d.roadmap.summary.readiness_now} />
          </div>

          {d.streak?.show !== false && <StreakCard initial={d.streak} />}

          <div className="card p-5">
            <SectionTitle eyebrow="Self-awareness" title="Confidence vs. results" />
            {d.calibration.n === 0 ? <div className="text-sm text-muted">Rate how sure you are before answering — SAARTHI will show how well your confidence matches your results.</div> : (
              <div className="space-y-2">
                {(['low', 'mid', 'high'] as const).map(k => {
                  const b = d.calibration.bins[k]
                  return <div key={k} className="text-xs"><div className="flex justify-between font-semibold"><span>{k === 'low' ? 'Unsure (1–2)' : k === 'mid' ? 'Maybe (3)' : 'Sure (4–5)'}</span><span className="text-muted">{b.n ? `${b.correct}/${b.n} right` : '—'}</span></div><Bar value={b.accuracy ?? 0} color={k === 'high' && (b.accuracy ?? 1) < 0.6 ? '#c62828' : '#1f7a7a'} h={6} /></div>
                })}
                {d.calibration.message && <div className="text-sm font-semibold text-navy">{d.calibration.message}</div>}
              </div>
            )}
          </div>

          <div className="card p-5">
            <SectionTitle eyebrow="Chhatrachhaya" title="Your mentor cases" right={<DemoBadge label="demo mentors" />} />
            {d.cases.length === 0 ? <div className="text-sm text-muted">No cases yet. If you stay stuck, SAARTHI will suggest a human mentor and send them a full report.</div> :
              d.cases.slice(0, 3).map((c: any) => <Link key={c.id} to={'/mentors/' + c.id} className="block rounded-xl border border-line px-3 py-2 mb-2 hover:bg-paper text-sm"><b className="text-navy">{c.concept_name ?? 'Career guidance'}</b> <span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{c.status.replace('_', ' ')}</span><div className="text-xs text-muted">{c.mentor ? `with ${c.mentor.name}` : c.tier}</div></Link>)}
          </div>
        </div>
      </div>
    </div>
  )
}
