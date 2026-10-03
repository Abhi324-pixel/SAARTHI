import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { apiT05, Phase } from '../api_ext/T05'
import Checkpoints from '../components/Checkpoints'
import NavigationMap from '../components/NavigationMap'
import QuizRunner from '../components/QuizRunner'
import { Bar, Callout, FlagChip, LevelChip, SectionTitle, Spinner } from '../components/ui'
import { useApp } from '../store'

export default function Roadmap() {
  const { me, toast, bump, version, t } = useApp()
  const [rm, setRm] = useState<any | null>(null)
  const [viewMode, setViewMode] = useState<'map' | 'schedule'>('map')
  const [graph, setGraph] = useState<any[]>([])
  const [hours, setHours] = useState(6)
  const [weeks, setWeeks] = useState(12)
  const [wi, setWi] = useState<any | null>(null)
  const [q, setQ] = useState('')
  const [why, setWhy] = useState<any | null>(null)

  // T05 State
  const [settingDeadlineFor, setSettingDeadlineFor] = useState<string | null>(null)
  const [deadlineDate, setDeadlineDate] = useState('')
  const [deadlineBusy, setDeadlineBusy] = useState(false)
  const [activeCheck, setActiveCheck] = useState<{
    phaseKey: string
    phaseTitle: string
    items: any[]
  } | null>(null)
  const [checkingPhase, setCheckingPhase] = useState<string | null>(null)

  useEffect(() => {
    api.roadmap().then(r => {
      setRm(r)
      setHours(r.summary.weekly_hours)
      setWeeks(r.summary.total_weeks)
    }).catch(e => toast(e.message, 'err'))
    api.graph().then(g => setGraph(g.nodes)).catch(() => {})
  }, [version, toast])

  useEffect(() => {
    if (me) {
      if (me.weekly_hours) setHours(me.weekly_hours)
      if (me.horizon_weeks) setWeeks(me.horizon_weeks)
    }
  }, [me?.weekly_hours, me?.horizon_weeks])

  useEffect(() => {
    if (!rm) return
    const h = setTimeout(() => {
      api.whatIf(hours, weeks).then(setWi).catch(() => {})
    }, 200)
    return () => clearTimeout(h)
  }, [hours, weeks, rm])

  if (!rm) return <div className="py-20 flex justify-center"><Spinner label="Calculating your adaptive roadmap…" /></div>

  async function apply() {
    try {
      await api.updateMe({ weekly_hours: hours, horizon_weeks: weeks })
      const r = await api.roadmap()
      setRm(r)
      bump()
      toast('Schedule updated — roadmap rebuilt.')
    } catch (e: any) {
      toast(e.message, 'err')
    }
  }

  async function ask(conceptId: string) {
    try {
      const r = await api.whyNot(conceptId)
      setWhy(r)
    } catch (e: any) {
      toast(e.message, 'err')
    }
  }

  async function saveDeadline(phaseKey: string) {
    if (!deadlineDate) return
    setDeadlineBusy(true)
    try {
      await apiT05.setDeadline(phaseKey, deadlineDate)
      toast('Deadline set!', 'ok')
      setSettingDeadlineFor(null)
      setDeadlineDate('')
      bump()
    } catch (e: any) {
      toast(e.message || 'Failed to set deadline', 'err')
    } finally {
      setDeadlineBusy(false)
    }
  }

  async function clearDeadline(phaseKey: string) {
    try {
      await apiT05.deleteDeadline(phaseKey)
      toast('Deadline cleared', 'ok')
      bump()
    } catch (e: any) {
      toast(e.message || 'Failed to clear deadline', 'err')
    }
  }

  async function startPhaseCheck(phase: Phase) {
    setCheckingPhase(phase.key)
    try {
      const res = await apiT05.phaseCheck(phase.key)
      if (!res.items || res.items.length === 0) {
        toast(`All concepts in "${phase.title}" are already at or above target mastery! 🎯`, 'ok')
      } else {
        setActiveCheck({
          phaseKey: phase.key,
          phaseTitle: phase.title,
          items: res.items,
        })
      }
    } catch (e: any) {
      toast(e.message || 'Failed to start phase check', 'err')
    } finally {
      setCheckingPhase(null)
    }
  }

  const items = (rm.items || []).filter((i: any) => i.kind !== 'review')
  const reviews = (rm.items || []).filter((i: any) => i.kind === 'review')
  const byWeek: Record<number, any[]> = {}
  items.forEach((i: any) => { (byWeek[i.week] ||= []).push(i) })
  const matches = q.trim() ? graph.filter(n => n.name.toLowerCase().includes(q.toLowerCase())).slice(0, 5) : []
  const changed = wi && JSON.stringify(wi.scenario) !== JSON.stringify(wi.current)

  const phases: Phase[] = rm.phases || []
  const phasedWeeks = new Set(phases.flatMap(p => Array.from({ length: p.end_week - p.start_week + 1 }, (_, i) => p.start_week + i)))
  const unphasedWeeks = Object.keys(byWeek).map(Number).filter(w => !phasedWeeks.has(w)).sort((a, b) => a - b)

  const renderWeekSection = (wk: number) => {
    const list = byWeek[wk]
    if (!list || list.length === 0) return null
    return (
      <section key={wk} className="card p-5">
        <div className="flex items-center justify-between pb-3 border-b border-[rgba(210,225,235,0.12)]">
          <h3 className="font-extrabold text-white text-base lg:text-lg heading-glow">Week {wk}</h3>
          <span className="chip text-xs" style={{ background: 'rgba(210, 225, 235, 0.08)', color: '#AEBBC5' }}>
            {(list as any[]).reduce((a, i) => a + i.minutes, 0)} min total
          </span>
        </div>
        <ol className="mt-3 divide-y divide-[var(--border-subtle)]">
          {(list as any[]).map(i => (
            <li key={i.item_id} className="py-3.5">
              <div className="flex items-start gap-3.5">
                <span className="h-6 w-6 rounded-full bg-[rgba(255,138,36,0.18)] border border-[rgba(255,138,36,0.4)] text-[#FF8A24] text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i.order}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link to={'/learn/' + i.concept_id} className="font-bold text-white hover:text-[#FF8A24] transition-colors">
                      {i.title}
                    </Link>
                    <LevelChip level={i.level} />
                    {i.flags?.map((f: string) => <FlagChip key={f} flag={f} />)}
                    {i.status === 'done' && (
                      <span className="chip" style={{ background: 'rgba(53, 208, 127, 0.15)', color: '#35D07F', border: '1px solid rgba(53, 208, 127, 0.3)' }}>
                        ✓ at target
                      </span>
                    )}
                    <span className="text-xs text-slate-400 ml-auto desc-glow font-mono">{i.minutes} min</span>
                  </div>
                  <div className="mt-2 rounded-xl bg-[rgba(20,32,44,0.6)] border border-[rgba(210,225,235,0.12)] px-3.5 py-2 text-sm text-slate-200 desc-glow">
                    <b className="text-[#FF8A24]">{t('whythis')}</b> {i.why}
                  </div>
                  <div className="mt-2 flex items-center gap-2.5 text-xs text-slate-400 desc-glow">
                    <span>{Math.round(i.p_now * 100)}% now</span>
                    <div className="w-28">
                      <Bar value={i.p_now / (i.target || 1)} h={5} />
                    </div>
                    <span>target {Math.round(i.target * 100)}%</span>
                    <span className="ml-2 text-slate-400">steps: {i.steps.join(' → ').replace('_', ' ')}</span>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>
    )
  }

  return (
    <div className="space-y-6">
      <div className="card p-6 lg:p-8 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="eyebrow">{viewMode === 'map' ? 'Adaptive guidance · always explained' : `Version ${rm.version} · always explained`}</div>
            <h1 className="h-page heading-glow mt-1">{viewMode === 'map' ? 'Google Maps for Learning' : 'Your adaptive roadmap'}</h1>
          </div>
          <div className="flex items-center gap-1 p-1 rounded-xl border border-line" role="tablist" aria-label="Roadmap view">
            <button type="button" role="tab" aria-selected={viewMode === 'map'} onClick={() => setViewMode('map')}
              className={`px-4 py-2 text-xs font-black rounded-lg ${viewMode === 'map' ? 'bg-navy text-white' : 'text-muted'}`}>🧭 Interactive GPS Map</button>
            <button type="button" role="tab" aria-selected={viewMode === 'schedule'} onClick={() => setViewMode('schedule')}
              className={`px-4 py-2 text-xs font-black rounded-lg ${viewMode === 'schedule' ? 'bg-navy text-white' : 'text-muted'}`}>📋 Weekly Schedule & Phases</button>
          </div>
        </div>
        <p className="text-slate-300 desc-glow max-w-3xl leading-relaxed">
          {viewMode === 'map'
            ? 'Real-time navigation through your knowledge graph, worked out from your own evidence, the prerequisites each topic needs, and the mistakes found in your work.'
            : "Built from your Learner Twin by rules you can audit — not by a chatbot's opinion. Every step shows its reason; when new evidence changes the plan, you'll see exactly what changed and why."}
        </p>
      </div>

      {viewMode === 'map' ? (
        <NavigationMap />
      ) : (
        <>
      {rm.change_reason && <Callout tone="saffron" title="Latest change" icon="↻">{rm.change_reason}</Callout>}

      {/* Active Phase Check QuizRunner */}
      {activeCheck && (
        <div className="card p-6 border border-[#4D9DFF]/40 bg-[rgba(12,35,51,0.6)] space-y-4 shadow-xl">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="eyebrow">Phase Check · {activeCheck.phaseTitle}</div>
              <h2 className="text-xl font-extrabold text-white heading-glow">Check me on this phase</h2>
              <p className="text-xs text-slate-300 desc-glow mt-1">
                Answer these diagnostic questions across concepts in this phase that need reinforcement. Answering gives real evidence that moves your mastery!
              </p>
            </div>
            <button
              onClick={() => setActiveCheck(null)}
              className="text-xs text-slate-400 hover:text-white underline shrink-0 font-medium"
            >
              Close check
            </button>
          </div>
          <QuizRunner
            total={activeCheck.items.length}
            fixedItems={activeCheck.items}
            title={`Check: ${activeCheck.phaseTitle}`}
            onFinish={() => {
              toast(`Phase check for "${activeCheck.phaseTitle}" completed! Mastery updated.`, 'ok')
              setActiveCheck(null)
              bump()
            }}
          />
        </div>
      )}

      <div className="grid lg:grid-cols-12 gap-5">
        <div className="lg:col-span-8 space-y-5 min-w-0">
          {(rm.summary.n_reviews > 0 || reviews.length > 0) && (
            <div className="card p-5 border-[rgba(77,157,255,0.35)] bg-[rgba(77,157,255,0.08)]">
              <div className="font-extrabold text-white heading-glow">🔁 {reviews.length || rm.summary.n_reviews} review(s) due</div>
              <div className="text-sm text-slate-300 desc-glow mt-1">
                Quick re-checks so concepts you learned don't fade.{' '}
                <Link to="/reviews" className="text-[#4D9DFF] font-bold underline hover:text-white">Start reviews</Link>
              </div>
            </div>
          )}

          {/* Phases Display */}
          {phases.length > 0 ? (
            <div className="space-y-6">
              {phases.map((p, idx) => {
                const phaseWeeks = []
                for (let w = p.start_week; w <= p.end_week; w++) {
                  if (byWeek[w]) phaseWeeks.push(w)
                }

                return (
                  <div key={p.key} className="space-y-4 p-5 rounded-2xl bg-[rgba(15,25,35,0.45)] border border-[rgba(210,225,235,0.14)] backdrop-blur-md">
                    {/* Phase Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[rgba(210,225,235,0.12)] pb-3.5">
                      <div>
                        <div className="text-xs font-bold text-[#4D9DFF] uppercase tracking-wide">
                          Phase {idx + 1} · Weeks {p.start_week}–{p.end_week}
                        </div>
                        <h2 className="text-lg font-extrabold text-white heading-glow">{p.title}</h2>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          type="button"
                          disabled={checkingPhase === p.key}
                          onClick={() => startPhaseCheck(p)}
                          className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
                          title="Run a short mixed check across this phase's concepts"
                        >
                          {checkingPhase === p.key ? 'Loading…' : `✓ ${t('T05.check_me')}`}
                        </button>
                      </div>
                    </div>

                    {/* Dates & Deadline Info */}
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs py-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="chip" style={{ background: 'rgba(77, 157, 255, 0.15)', color: '#4D9DFF', border: '1px solid rgba(77, 157, 255, 0.3)' }}>
                          🎯 {t('T05.target_date')}: <b>{p.target_date}</b>
                        </span>

                        {p.deadline ? (
                          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-[rgba(255,181,46,0.4)] bg-[rgba(255,181,46,0.12)] text-[#FFB52E]">
                            <span>📅 {t('T05.deadline')}: <b>{p.deadline}</b></span>
                            <button
                              type="button"
                              onClick={() => { setSettingDeadlineFor(p.key); setDeadlineDate(p.deadline || '') }}
                              className="text-[#FF8A24] hover:underline ml-1 font-semibold"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => clearDeadline(p.key)}
                              className="text-slate-400 hover:text-red-400 ml-0.5"
                              title="Clear deadline"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => { setSettingDeadlineFor(p.key); setDeadlineDate('') }}
                            className="text-[#4D9DFF] font-semibold hover:underline"
                          >
                            + Set deadline
                          </button>
                        )}
                      </div>

                      <span className="text-slate-400 desc-glow font-mono">{p.minutes} min planned</span>
                    </div>

                    {/* Deadline Editor Form */}
                    {settingDeadlineFor === p.key && (
                      <div className="p-3.5 card rounded-xl border border-[var(--border-subtle)] flex items-center gap-2.5 flex-wrap">
                        <span className="text-xs font-semibold text-white">Set deadline for {p.title}:</span>
                        <input
                          type="date"
                          className="input text-xs py-1 px-2.5 w-auto"
                          value={deadlineDate}
                          onChange={e => setDeadlineDate(e.target.value)}
                        />
                        <button
                          type="button"
                          disabled={deadlineBusy || !deadlineDate}
                          onClick={() => saveDeadline(p.key)}
                          className="btn btn-primary text-xs py-1 px-3"
                        >
                          {deadlineBusy ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setSettingDeadlineFor(null)}
                          className="btn btn-secondary text-xs py-1 px-3"
                        >
                          Cancel
                        </button>
                      </div>
                    )}

                    {/* Deadline Status Callout */}
                    {p.deadline && p.deadline_status && (
                      <div>
                        {p.deadline_status.passed ? (
                          <div className="p-3 rounded-xl bg-[rgba(255,83,100,0.12)] border border-[rgba(255,83,100,0.3)] text-xs text-red-200">
                            ⚠ This deadline has passed. Choose a future date.
                          </div>
                        ) : p.deadline_status.on_track ? (
                          <div className="p-3 rounded-xl bg-[rgba(53,208,127,0.12)] border border-[rgba(53,208,127,0.3)] text-xs flex items-center gap-2 flex-wrap">
                            <span className="chip" style={{ background: 'rgba(53, 208, 127, 0.2)', color: '#35D07F' }}>
                              ✓ {t('T05.on_track')}
                            </span>
                            <span className="text-slate-200 desc-glow">
                              At {hours} h/week, projected finish is <b>{p.deadline_status.projected_finish}</b> ({p.deadline_status.gap_days} days before your deadline).
                            </span>
                          </div>
                        ) : (
                          <div className="p-3 rounded-xl bg-[rgba(255,181,46,0.12)] border border-[rgba(255,181,46,0.3)] text-xs space-y-1.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="chip" style={{ background: 'rgba(255, 181, 46, 0.2)', color: '#FFB52E' }}>
                                ⚠ {t('T05.behind')}
                              </span>
                              <span className="text-slate-200 font-medium desc-glow">
                                At {hours} h/wk, finishes around <b>{p.deadline_status.projected_finish}</b> ({p.deadline_status.gap_days} days after deadline).
                              </span>
                            </div>
                            <div className="text-slate-400 text-[11px] desc-glow">
                              To make it: raise to{' '}
                              <button
                                type="button"
                                onClick={() => setHours(p.deadline_status!.needed_hours_per_week)}
                                className="text-[#FF8A24] font-extrabold underline cursor-pointer"
                                title="Click to test this in What-If time changer"
                              >
                                {p.deadline_status.needed_hours_per_week} h/week
                              </button>{' '}
                              (click to test in what-if), or extend the deadline date.
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Weeks in this phase */}
                    <div className="space-y-3 pt-2">
                      {phaseWeeks.map(wk => renderWeekSection(wk))}
                    </div>
                  </div>
                )
              })}

              {/* Any unphased weeks if edge case */}
              {unphasedWeeks.map(wk => renderWeekSection(wk))}
            </div>
          ) : (
            /* Fallback to flat week list if no phases defined */
            Object.keys(byWeek).map(Number).sort((a, b) => a - b).map(wk => renderWeekSection(wk))
          )}

          {rm.summary?.dropped?.length > 0 && (
            <div className="card p-5">
              <div className="font-extrabold text-white heading-glow">Not in this plan (time budget)</div>
              <div className="text-sm text-slate-300 desc-glow mt-1">
                {rm.summary.dropped.map((d: any) => d.name).join(' · ')}. Raise your weekly hours to include them.
              </div>
            </div>
          )}

          <div className="card p-5">
            <SectionTitle eyebrow="History" title="How this plan changed" />
            <ol className="space-y-2.5 mt-2">
              {rm.history?.map((h: any) => (
                <li key={h.version} className="text-sm border-l-2 border-[#FF8A24]/40 pl-3">
                  <b className="text-white">v{h.version}</b> <span className="text-slate-400 text-xs ml-1">{h.at}</span>
                  <div className="text-slate-300 desc-glow mt-0.5">{h.reason}</div>
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* Aside */}
        <aside className="lg:col-span-4 space-y-5 lg:sticky lg:top-20 h-fit">
          {/* T05 Personal Checkpoints */}
          <Checkpoints />

          {/* What if time changer */}
          <div className="card p-5 space-y-4">
            <SectionTitle eyebrow="What if…" title="Change your schedule" />
            <label className="block text-sm font-semibold text-slate-200 desc-glow">
              Hours per week: <b className="text-[#FF8A24]">{hours}</b>
              <input type="range" min={1} max={30} value={hours} onChange={e => setHours(+e.target.value)} className="w-full accent-[#FF8A24] mt-1" />
            </label>
            <label className="block text-sm font-semibold text-slate-200 desc-glow">
              Target weeks: <b className="text-[#FF8A24]">{weeks}</b>
              <input type="range" min={2} max={40} value={weeks} onChange={e => setWeeks(+e.target.value)} className="w-full accent-[#FF8A24] mt-1" />
            </label>
            {wi && (
              <div className="rounded-xl bg-[rgba(20,32,44,0.7)] border border-[rgba(210,225,235,0.14)] p-3.5 text-sm space-y-1.5 desc-glow">
                <div className="text-slate-200">
                  <b>{wi.scenario.n_items}</b> topics in {wi.scenario.total_weeks} wk <span className="text-slate-400">(now {wi.current.n_items} in {wi.current.total_weeks})</span>
                </div>
                <div className="text-slate-200">
                  Readiness after plan: <b className="text-white">{Math.round(wi.scenario.readiness_after * 100)}%</b> <span className="text-slate-400">(now {Math.round(wi.current.readiness_after * 100)}%)</span>
                </div>
                {wi.diff.added.length > 0 && (
                  <div className="text-[#35D07F] font-semibold text-xs">
                    + {wi.diff.added.slice(0, 4).map((a: any) => a.title).join(', ')}{wi.diff.added.length > 4 ? '…' : ''}
                  </div>
                )}
                {wi.diff.removed.length > 0 && (
                  <div className="text-[#FF5364] font-semibold text-xs">
                    − {wi.diff.removed.slice(0, 4).map((a: any) => a.title).join(', ')}
                  </div>
                )}
                {!changed && <div className="text-slate-400 text-xs">Same plan as current.</div>}
              </div>
            )}
            <button className="btn btn-primary w-full" onClick={apply} disabled={!changed}>
              Apply this schedule
            </button>
          </div>

          {/* Topic search / Why Not */}
          <div className="card p-5 space-y-3">
            <SectionTitle eyebrow="Curriculum Audit" title="Why isn't X in my plan?" />
            <input className="input" placeholder="Search a topic, e.g. Docker" value={q} onChange={e => { setQ(e.target.value); setWhy(null) }} aria-label="Search a topic" />
            {matches.map(m => (
              <button key={m.id} className="block w-full text-left rounded-xl px-3.5 py-2.5 hover:bg-[rgba(255,255,255,0.06)] text-sm font-semibold text-white border border-transparent hover:border-[rgba(210,225,235,0.16)] transition-all" onClick={() => { ask(m.id); setQ('') }}>
                {m.name}
              </button>
            ))}
            {why && (
              <Callout tone="navy" title={graph.find(n => n.id === why.concept_id)?.name}>
                {why.text}
                <div className="text-[11px] text-slate-400 mt-1 font-mono">
                  reason code: {why.code} (computed from the skill graph and your time budget)
                </div>
              </Callout>
            )}
          </div>
        </aside>
      </div>
        </>
      )}
    </div>
  )
}
