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

  useEffect(() => { 
    api.dashboard().then(setD).catch(e => toast(e.message, 'err')) 
  }, [version, toast])

  if (!d) return <div className="py-20 flex justify-center"><Spinner label="Reading your Learner Twin from database…" /></div>

  const nodeById = Object.fromEntries(d.graph.nodes.map((n: any) => [n.id, n]))
  const selNode = sel ? nodeById[sel] : null
  const mis = d.misconceptions.filter((m: any) => ['confirmed', 'correcting', 'pending_verify'].includes(m.status))
  const cand = d.misconceptions.filter((m: any) => m.status === 'candidate')
  const missionIcon: Record<string, string> = { fix_misconception: '🛠', review: '🔁', learn: '📘' }

  async function askMentor(s: any) {
    try { 
      const c = await api.createCase({ category: s.category, concept_id: s.concept_id, reason: s.reason, trigger: s.trigger })
      toast('Case opened with a full report.')
      nav('/mentors/' + c.case_id) 
    } catch (e: any) { 
      toast(e.message, 'err') 
    }
  }

  return (
    <div className="space-y-6">
      {/* 1. HERO / WELCOME SECTION (Dark Glass, Eyebrow, White Illuminated Heading, Orange CTA) */}
      <div className="card p-6 lg:p-8 flex flex-col lg:flex-row justify-between lg:items-center gap-6 relative overflow-hidden">
        {/* Subtle orange atmospheric ambient light */}
        <div className="absolute -right-16 -top-16 w-64 h-64 rounded-full bg-[rgba(255,138,36,0.10)] blur-3xl pointer-events-none" aria-hidden />
        <div className="relative max-w-2xl">
          <div className="eyebrow mb-2 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-[#FF8A24] animate-pulse" />
            <span>{d.role.title}</span>
            <span className="text-slate-500">·</span>
            <span className="text-slate-300 font-semibold">{me?.weekly_hours}h/week target</span>
          </div>
          <h1 className="h-page text-2xl sm:text-3xl lg:text-4xl font-extrabold text-white heading-glow">
            {me?.language === 'english' ? (
              <>Welcome back, <span className="text-[#FF8A24]">{me?.name?.split(' ')[0]}</span></>
            ) : (
              <>Namaste, <span className="text-[#FF8A24]">{me?.name?.split(' ')[0]}</span> 🙏</>
            )}
          </h1>
          <p className="mt-2 text-slate-300 text-sm sm:text-base leading-relaxed desc-glow">
            {d.has_evidence 
              ? 'Your Learner Twin updates continuously from every line of SQL you write, quiz answers, and spoken explanations.' 
              : 'Begin with the placement assessment so SAARTHI can discover where you stand and blueprint your curriculum.'}
          </p>
        </div>
        <div className="relative flex gap-3 flex-wrap shrink-0 items-center">
          <Link to="/placement" className="btn btn-primary">Take a quick check</Link>
          <Link to="/practice" className="btn btn-ghost">Practise SQL</Link>
          <button 
            className="btn btn-ghost" 
            onClick={() => nav('/learn/' + (mis[0]?.concept_id ?? d.mission[0]?.concept_id ?? 'sql_outer_join') + '#teachback')}
          >
            🎙 {t('teachback')}
          </button>
        </div>
      </div>

      {/* 2. MAIN DASHBOARD GRID: Left Progress Analytics Panel, Right Mission / Tasks */}
      <div className="grid lg:grid-cols-12 gap-5">
        {/* Left: Progress / current state */}
        <div className="card p-6 lg:col-span-5 flex flex-col justify-between">
          <SectionTitle eyebrow="Learner Twin Analytics" title={`Progress to ${d.role.title}`} />
          <div className="flex flex-col sm:flex-row items-center gap-6 my-auto py-2">
            <Ring value={d.overall} size={118} stroke={11} sub="to goal" />
            <div className="min-w-0 w-full space-y-2">
              <div className="text-xs font-bold text-slate-300 desc-glow uppercase tracking-wider">Concept Mastery</div>
              <div className="text-sm space-y-1.5">
                {(['mastered', 'proficient', 'developing', 'unknown'] as const).map(k => (
                  <div key={k} className="flex items-center justify-between gap-2">
                    <LevelChip level={k} />
                    <b className="text-white font-mono text-sm">{d.levels[k]}</b>
                  </div>
                ))}
                <div className="text-xs text-slate-400 pt-1 desc-glow border-t border-[rgba(210,225,235,0.12)]">
                  {d.levels.not_assessed} concept(s) not assessed yet
                </div>
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

        {/* Right: Today's mission / task rows */}
        <div className="card p-6 lg:col-span-7 flex flex-col justify-between">
          <SectionTitle 
            eyebrow="Target Mission" 
            title={t('mission')} 
            right={d.due_reviews > 0 ? (
              <Link to="/reviews" className="chip backdrop-blur-sm" style={{ background: 'rgba(77, 157, 255, 0.15)', color: '#4D9DFF', border: '1px solid rgba(77, 157, 255, 0.35)' }}>
                {d.due_reviews} review(s) due →
              </Link>
            ) : undefined} 
          />
          <div className="space-y-2.5 mt-1">
            {d.mission.map((m: any, i: number) => (
              <button 
                key={i} 
                onClick={() => nav(m.type === 'review' ? '/reviews' : '/learn/' + m.concept_id)} 
                className="glass-row w-full text-left px-4 py-3.5 flex items-center justify-between gap-3 group"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <span className="w-9 h-9 rounded-xl bg-[rgba(25,39,51,0.7)] border border-[rgba(210,225,235,0.16)] flex items-center justify-center text-lg shrink-0 group-hover:border-[#FF8A24]/40 group-hover:shadow-[0_0_8px_rgba(255,138,36,0.25)] transition-all" aria-hidden>
                    {missionIcon[m.type] ?? '📘'}
                  </span>
                  <div className="min-w-0">
                    <span className="font-bold text-white group-hover:text-[#FF8A24] block truncate transition-colors">
                      {m.title}
                    </span>
                    <span className="text-xs text-slate-400 block truncate desc-glow mt-0.5">
                      {m.reason}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="chip text-[11px] font-mono" style={{ background: 'rgba(210, 225, 235, 0.08)', color: '#AEBBC5' }}>
                    {m.minutes} min
                  </span>
                  <span className="row-arrow text-slate-400 text-sm font-bold transition-all">→</span>
                </div>
              </button>
            ))}
            {!d.mission.length && (
              <div className="text-sm text-slate-400 desc-glow py-6 text-center">
                You're all caught up. Try a mock interview or a teach-back to deepen what you know.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3. MISCONCEPTIONS & ESCALATIONS */}
      {(mis.length > 0 || cand.length > 0 || d.escalation_suggestions.length > 0) && (
        <div className="grid md:grid-cols-2 gap-5">
          {mis.map((m: any) => (
            <div key={m.instance_id} className="card p-5 border-[rgba(168,85,247,0.35)] bg-[rgba(168,85,247,0.08)]">
              <div className="flex items-center gap-2 flex-wrap">
                <FlagChip flag="misconception" />
                <span className="chip" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#C084FC', border: '1px solid rgba(168, 85, 247, 0.35)' }}>
                  {m.status.replace('_', ' ')}
                </span>
              </div>
              <div className="font-extrabold text-[#C084FC] text-base mt-2.5 heading-glow">{m.name}</div>
              <div className="text-sm text-slate-200 mt-1 desc-glow">{m.description}</div>
              <div className="text-xs text-slate-400 mt-1 desc-glow">in {m.concept_name} · {m.cycles} correction cycle(s) so far</div>
              <div className="flex gap-2.5 mt-3.5 flex-wrap">
                <Link to={'/learn/' + m.concept_id} className="btn btn-primary btn-sm">Fix it now</Link>
                <button 
                  className="btn btn-ghost btn-sm" 
                  onClick={async () => { 
                    try { 
                      await api.disputeMis(m.instance_id)
                      toast('Removed — thanks for correcting me.')
                      bump() 
                    } catch (e: any) { 
                      toast(e.message, 'err') 
                    } 
                  }}
                >
                  This isn't right
                </button>
              </div>
            </div>
          ))}
          {cand.map((m: any) => (
            <div key={m.instance_id} className="card p-5 border-[rgba(255,181,46,0.35)] bg-[rgba(255,181,46,0.08)]">
              <div className="chip" style={{ background: 'rgba(255, 181, 46, 0.15)', color: '#FFB52E', border: '1px solid rgba(255, 181, 46, 0.35)' }}>
                Possible misconception — needs confirmation
              </div>
              <div className="font-bold text-white mt-2.5 heading-glow">{m.name}</div>
              {m.statement && <div className="text-sm text-slate-200 mt-1 desc-glow">You said: “{m.statement}”</div>}
              <div className="flex gap-2.5 mt-3.5">
                <button className="btn btn-primary btn-sm" onClick={async () => { await api.confirmMis(m.instance_id, true); bump() }}>Yes, that's what I think</button>
                <button className="btn btn-ghost btn-sm" onClick={async () => { await api.confirmMis(m.instance_id, false); bump() }}>No</button>
              </div>
            </div>
          ))}
          {d.escalation_suggestions.map((s: any, i: number) => (
            <Callout key={i} tone="navy" title="A human mentor could help here" icon="🤝">
              {s.reason}
              <div className="mt-2.5">
                <button className="btn btn-primary btn-sm" onClick={() => askMentor(s)}>Open a mentor case (with full report)</button>
              </div>
            </Callout>
          ))}
        </div>
      )}

      {/* 4. LOWER SECTIONS: Skill graph & Right Sidebar */}
      <div className="grid xl:grid-cols-12 gap-5">
        <div className="card p-6 xl:col-span-8 min-w-0">
          <SectionTitle 
            eyebrow="Skill graph" 
            title="Knowledge Architecture & Blockers" 
            right={<span className="text-xs text-slate-400 desc-glow">Click any concept to inspect</span>} 
          />
          <SkillGraph nodes={d.graph.nodes} edges={d.graph.edges} onSelect={id => setSel(id)} highlight={sel} />
          {selNode && (
            <div className="mt-4 rounded-xl bg-[rgba(20,32,44,0.85)] border border-[rgba(210,225,235,0.18)] p-3.5 flex items-center gap-3 flex-wrap pop shadow-md">
              <b className="text-white heading-glow">{selNode.name}</b>
              <LevelChip level={selNode.level} />
              {selNode.flags.map((f: string) => <FlagChip key={f} flag={f} />)}
              <span className="text-xs text-slate-400 desc-glow font-mono">
                {Math.round(selNode.p * 100)}%{selNode.target ? ` of ${Math.round(selNode.target * 100)}% target` : ''}
              </span>
              <Link to={'/learn/' + selNode.id} className="btn btn-primary btn-sm ml-auto">Open</Link>
            </div>
          )}
        </div>

        <div className="xl:col-span-4 space-y-5">
          {/* Roadmap Snapshot Card */}
          <div className="card p-5">
            <SectionTitle 
              eyebrow="Roadmap" 
              title={`v${d.roadmap.version} · ${d.roadmap.summary.total_weeks} weeks`} 
              right={<Link to="/roadmap" className="text-sm font-bold text-[#4D9DFF] hover:underline">All →</Link>} 
            />
            {d.roadmap.change_reason && (
              <div className="text-xs bg-[rgba(255,138,36,0.12)] border border-[rgba(255,138,36,0.30)] rounded-xl p-2.5 mb-3 text-slate-200 desc-glow">
                <b className="text-[#FF8A24]">Latest change:</b> {d.roadmap.change_reason}
              </div>
            )}
            <ol className="space-y-2.5">
              {d.roadmap.next.map((i: any) => (
                <li key={i.item_id} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span className="h-5 w-5 rounded-full bg-[rgba(255,138,36,0.2)] border border-[rgba(255,138,36,0.4)] text-[#FF8A24] text-[11px] font-bold flex items-center justify-center shrink-0">
                      {i.order}
                    </span>
                    <Link to={'/learn/' + i.concept_id} className="font-bold text-white hover:text-[#FF8A24] truncate transition-colors">
                      {i.title}
                    </Link>
                    {i.kind === 'fix_misconception' && <FlagChip flag="misconception" />}
                  </div>
                  <div className="text-xs text-slate-400 ml-7 desc-glow">week {i.week} · {i.minutes} min</div>
                </li>
              ))}
            </ol>
            <div className="mt-4 pt-3 border-t border-[rgba(210,225,235,0.12)]">
              <div className="flex justify-between text-xs text-slate-300 desc-glow mb-1.5">
                <span>Readiness now: <b className="text-white">{Math.round(d.roadmap.summary.readiness_now * 100)}%</b></span>
                <span>Target: <b className="text-[#35D07F]">{Math.round(d.roadmap.summary.readiness_after * 100)}%</b></span>
              </div>
              <Bar value={d.roadmap.summary.readiness_now} color="#FF8A24" />
            </div>
          </div>

          {d.streak?.show !== false && <StreakCard initial={d.streak} />}

          {/* Calibration / Self-awareness Card */}
          <div className="card p-5">
            <SectionTitle eyebrow="Metacognition" title="Confidence vs. accuracy" />
            {d.calibration.n === 0 ? (
              <div className="text-sm text-slate-400 desc-glow">
                Rate how sure you are before answering — SAARTHI will graph how well your confidence matches your actual accuracy.
              </div>
            ) : (
              <div className="space-y-2.5">
                {(['low', 'mid', 'high'] as const).map(k => {
                  const b = d.calibration.bins[k]
                  return (
                    <div key={k} className="text-xs space-y-1">
                      <div className="flex justify-between font-semibold">
                        <span className="text-slate-200">{k === 'low' ? 'Unsure (1–2)' : k === 'mid' ? 'Maybe (3)' : 'Sure (4–5)'}</span>
                        <span className="text-slate-400 font-mono">{b.n ? `${b.correct}/${b.n} right` : '—'}</span>
                      </div>
                      <Bar value={b.accuracy ?? 0} color={k === 'high' && (b.accuracy ?? 1) < 0.6 ? '#FF5364' : '#4D9DFF'} h={6} />
                    </div>
                  )
                })}
                {d.calibration.message && <div className="text-xs font-semibold text-slate-200 mt-2 desc-glow">{d.calibration.message}</div>}
              </div>
            )}
          </div>

          {/* Mentor Cases Card */}
          <div className="card p-5">
            <SectionTitle eyebrow="SAKHA" title="Your mentor cases" right={<DemoBadge label="demo mentors" />} />
            {d.cases.length === 0 ? (
              <div className="text-sm text-slate-400 desc-glow">
                No cases yet. If you stay stuck, SAARTHI will suggest a human mentor and generate a full diagnostic case report.
              </div>
            ) : (
              d.cases.slice(0, 3).map((c: any) => (
                <Link key={c.id} to={'/mentors/' + c.id} className="block glass-row px-3.5 py-2.5 mb-2 text-sm group">
                  <div className="flex items-center justify-between gap-2">
                    <b className="text-white group-hover:text-[#FF8A24] transition-colors">{c.concept_name ?? 'Career guidance'}</b>
                    <span className="chip" style={{ background: 'rgba(210, 225, 235, 0.08)', color: '#AEBBC5' }}>
                      {c.status.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 desc-glow mt-0.5">{c.mentor ? `with ${c.mentor.name}` : c.tier}</div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
