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
  const { me, version, toast, bump, t } = useApp()
  const [viewMode, setViewMode] = useState<'map' | 'schedule'>('map')
  const [rm, setRm] = useState<any | null>(null)
  const [hours, setHours] = useState<number>(me?.weekly_hours ?? 6)
  const [weeks, setWeeks] = useState<number>(me?.horizon_weeks ?? 12)
  const [wi, setWi] = useState<any | null>(null)
  const [why, setWhy] = useState<any | null>(null)
  const [q, setQ] = useState('')
  const [graph, setGraph] = useState<any[]>([])

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

  useEffect(() => { api.roadmap().then(setRm).catch(e => toast(e.message, 'err')) }, [version, toast])
  useEffect(() => { api.graph().then(g => setGraph(g.nodes)) }, [])
  useEffect(() => { if (me) { setHours(me.weekly_hours); setWeeks(me.horizon_weeks) } }, [me?.weekly_hours, me?.horizon_weeks])

  useEffect(() => {
    const id = setTimeout(() => { api.whatIf(hours, weeks).then(setWi).catch(() => {}) }, 250)
    return () => clearTimeout(id)
  }, [hours, weeks, version])

  async function apply() {
    try {
      await api.updateMe({ weekly_hours: hours, horizon_weeks: weeks })
      toast('Schedule updated — roadmap rebuilt.')
      bump()
    } catch (e: any) {
      toast(e.message, 'err')
    }
  }

  async function ask(id: string) {
    try {
      setWhy(await api.whyNot(id))
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

  if (!rm) return <div className="py-16 flex justify-center"><Spinner label="Building your roadmap…" /></div>

  const items = rm.items.filter((i: any) => i.kind !== 'review')
  const reviews = rm.items.filter((i: any) => i.kind === 'review')
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
      <section key={wk} className="card p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-extrabold text-navy">Week {wk}</h3>
          <span className="text-xs text-muted">{(list as any[]).reduce((a, i) => a + i.minutes, 0)} min</span>
        </div>
        <ol className="mt-2 divide-y divide-line">
          {(list as any[]).map(i => (
            <li key={i.item_id} className="py-3">
              <div className="flex items-start gap-3">
                <span className="h-6 w-6 rounded-full bg-navy text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i.order}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link to={'/learn/' + i.concept_id} className="font-bold text-navy hover:underline">
                      {i.title}
                    </Link>
                    <LevelChip level={i.level} />
                    {i.flags?.map((f: string) => <FlagChip key={f} flag={f} />)}
                    {i.status === 'done' && (
                      <span className="chip" style={{ background: '#d3efd6', color: '#124a17' }}>
                        ✓ at target
                      </span>
                    )}
                    <span className="text-xs text-muted ml-auto">{i.minutes} min</span>
                  </div>
                  <div className="mt-1.5 rounded-lg bg-paper px-3 py-2 text-sm">
                    <b className="text-saffron">{t('whythis')}</b> {i.why}
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-xs text-muted">
                    <span>{Math.round(i.p_now * 100)}% now</span>
                    <div className="w-28">
                      <Bar value={i.p_now / (i.target || 1)} h={5} />
                    </div>
                    <span>target {Math.round(i.target * 100)}%</span>
                    <span className="ml-2">steps: {i.steps.join(' → ').replace('_', ' ')}</span>
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
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4 flex-wrap border-b border-line pb-4">
        <div>
          <div className="eyebrow">Adaptive Guidance · Always Explained</div>
          <h1 className="h-page">
            {viewMode === 'map' ? 'Google Maps for Learning' : 'Your Adaptive Roadmap'}
          </h1>
          <p className="text-muted mt-1 max-w-3xl">
            {viewMode === 'map'
              ? 'Real-time GPS navigation through your knowledge graph. Computed deterministically from your BKT mastery, active prerequisites, and detected misconceptions.'
              : "Built from your Learner Twin by rules you can audit — not by a chatbot's opinion. Every step shows its reason; when new evidence changes the plan, you'll see exactly what changed and why."}
          </p>
        </div>

        <div className="flex items-center p-1 bg-paper border border-line rounded-xl shadow-sm">
          <button
            type="button"
            onClick={() => setViewMode('map')}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-black rounded-lg transition ${
              viewMode === 'map'
                ? 'bg-navy text-white shadow'
                : 'text-muted hover:text-navy'
            }`}
          >
            <span>🧭 Interactive GPS Map</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode('schedule')}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-black rounded-lg transition ${
              viewMode === 'schedule'
                ? 'bg-navy text-white shadow'
                : 'text-muted hover:text-navy'
            }`}
          >
            <span>📋 Weekly Schedule & Phases</span>
          </button>
        </div>
      </div>

      {viewMode === 'map' ? (
        <NavigationMap />
      ) : (
        <>
          {rm.change_reason && <Callout tone="saffron" title="Latest change" icon="↻">{rm.change_reason}</Callout>}

          {/* Active Phase Check QuizRunner */}
          {activeCheck && (
            <div className="card p-6 border-2 border-teal bg-paper space-y-4 shadow-md">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="eyebrow">Phase Check · {activeCheck.phaseTitle}</div>
                  <h2 className="text-xl font-extrabold text-navy">Check me on this phase</h2>
                  <p className="text-xs text-muted mt-1">
                    Answer these diagnostic questions across concepts in this phase that need reinforcement. Answering gives real evidence that moves your mastery!
                  </p>
                </div>
                <button
                  onClick={() => setActiveCheck(null)}
                  className="text-xs text-muted hover:text-navy underline shrink-0 font-medium"
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

          <div className="grid lg:grid-cols-[1fr_340px] gap-5">
        <div className="space-y-6 min-w-0">
          {rm.summary.n_reviews > 0 && (
            <div className="card p-4" style={{ borderColor: '#9ad8e3' }}>
              <div className="font-extrabold text-navy">🔁 {reviews.length} review(s) due</div>
              <div className="text-sm text-muted">
                Quick re-checks so things you learned don't fade.{' '}
                <Link to="/reviews" className="text-teal font-bold underline">Start reviews</Link>
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
                  <div key={p.key} className="space-y-3 p-4 rounded-2xl bg-paper/50 border border-line">
                    {/* Phase Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line pb-3">
                      <div>
                        <div className="text-xs font-bold text-teal uppercase tracking-wide">
                          Phase {idx + 1} · Weeks {p.start_week}–{p.end_week}
                        </div>
                        <h2 className="text-lg font-extrabold text-navy">{p.title}</h2>
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
                        <span className="chip bg-blue-50 text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                          🎯 {t('T05.target_date')}: <b>{p.target_date}</b>
                        </span>

                        {p.deadline ? (
                          <div className="flex items-center gap-1.5 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200 px-2.5 py-1 rounded-full border border-amber-200 dark:border-amber-800">
                            <span>📅 {t('T05.deadline')}: <b>{p.deadline}</b></span>
                            <button
                              type="button"
                              onClick={() => { setSettingDeadlineFor(p.key); setDeadlineDate(p.deadline || '') }}
                              className="text-amber-700 hover:text-navy underline ml-1 font-semibold"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => clearDeadline(p.key)}
                              className="text-muted hover:text-red-600 ml-0.5"
                              title="Clear deadline"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => { setSettingDeadlineFor(p.key); setDeadlineDate('') }}
                            className="text-teal font-semibold hover:underline"
                          >
                            + Set deadline
                          </button>
                        )}
                      </div>

                      <span className="text-muted">{p.minutes} min planned</span>
                    </div>

                    {/* Deadline Editor Form */}
                    {settingDeadlineFor === p.key && (
                      <div className="p-3 bg-paper rounded-xl border border-line flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold text-navy">Set deadline for {p.title}:</span>
                        <input
                          type="date"
                          className="input text-xs py-1 px-2"
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
                          <div className="p-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-300">
                            ⚠ This deadline has passed. Choose a future date.
                          </div>
                        ) : p.deadline_status.on_track ? (
                          <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 text-xs flex items-center gap-2 flex-wrap">
                            <span className="chip" style={{ background: '#d3efd6', color: '#124a17' }}>
                              ✓ {t('T05.on_track')}
                            </span>
                            <span className="text-muted">
                              At {hours} h/week, projected finish is <b>{p.deadline_status.projected_finish}</b> ({p.deadline_status.gap_days} days before your deadline).
                            </span>
                          </div>
                        ) : (
                          <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="chip bg-amber-200 text-amber-900 font-bold">
                                ⚠ {t('T05.behind')}
                              </span>
                              <span className="text-amber-900 dark:text-amber-200 font-medium">
                                At {hours} h/wk, finishes around <b>{p.deadline_status.projected_finish}</b> ({p.deadline_status.gap_days} days after deadline).
                              </span>
                            </div>
                            <div className="text-muted text-[11px]">
                              To make it: raise to{' '}
                              <button
                                type="button"
                                onClick={() => setHours(p.deadline_status!.needed_hours_per_week)}
                                className="text-teal font-extrabold underline hover:text-navy cursor-pointer"
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

          {rm.summary.dropped.length > 0 && (
            <div className="card p-4">
              <div className="font-extrabold text-navy">Not in this plan (time budget)</div>
              <div className="text-sm text-muted mt-1">
                {rm.summary.dropped.map((d: any) => d.name).join(' · ')}. Raise your weekly hours to include them.
              </div>
            </div>
          )}

          <div className="card p-4">
            <SectionTitle eyebrow="History" title="How this plan changed" />
            <ol className="space-y-2">
              {rm.history.map((h: any) => (
                <li key={h.version} className="text-sm">
                  <b className="text-navy">v{h.version}</b> <span className="text-muted text-xs">{h.at}</span>
                  <div>{h.reason}</div>
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* Aside */}
        <aside className="space-y-4 lg:sticky lg:top-20 h-fit">
          {/* T05 Personal Checkpoints */}
          <Checkpoints />

          {/* What if time changer */}
          <div className="card p-4 space-y-3">
            <SectionTitle eyebrow="What if…" title="Change your time" />
            <label className="block text-sm font-semibold">
              Hours per week: <b className="text-saffron">{hours}</b>
              <input
                type="range"
                min={1}
                max={30}
                value={hours}
                onChange={e => setHours(+e.target.value)}
                className="w-full accent-[#e07a1f]"
              />
            </label>
            <label className="block text-sm font-semibold">
              Weeks: <b className="text-saffron">{weeks}</b>
              <input
                type="range"
                min={2}
                max={40}
                value={weeks}
                onChange={e => setWeeks(+e.target.value)}
                className="w-full accent-[#e07a1f]"
              />
            </label>
            {wi && (
              <div className="rounded-xl bg-paper p-3 text-sm space-y-1">
                <div>
                  <b>{wi.scenario.n_items}</b> topics in {wi.scenario.total_weeks} wk{' '}
                  <span className="text-muted">(now {wi.current.n_items} in {wi.current.total_weeks})</span>
                </div>
                <div>
                  Readiness after plan: <b>{Math.round(wi.scenario.readiness_after * 100)}%</b>{' '}
                  <span className="text-muted">(now {Math.round(wi.current.readiness_after * 100)}%)</span>
                </div>
                {wi.diff.added.length > 0 && (
                  <div className="text-lvl-proficient font-semibold">
                    + {wi.diff.added.slice(0, 4).map((a: any) => a.title).join(', ')}
                    {wi.diff.added.length > 4 ? '…' : ''}
                  </div>
                )}
                {wi.diff.removed.length > 0 && (
                  <div className="text-lvl-unknown font-semibold">
                    − {wi.diff.removed.slice(0, 4).map((a: any) => a.title).join(', ')}
                  </div>
                )}
                {!changed && <div className="text-muted">Same plan as now.</div>}
              </div>
            )}
            <button className="btn btn-primary w-full" onClick={apply} disabled={!changed}>
              Apply this schedule
            </button>
          </div>

          {/* Topic search / Why Not */}
          <div className="card p-4 space-y-2">
            <SectionTitle eyebrow="Ask" title="Why isn't X in my plan?" />
            <input
              className="input"
              placeholder="Search a topic, e.g. Docker"
              value={q}
              onChange={e => { setQ(e.target.value); setWhy(null) }}
              aria-label="Search a topic"
            />
            {matches.map(m => (
              <button
                key={m.id}
                className="block w-full text-left rounded-lg px-3 py-2 hover:bg-paper text-sm font-semibold"
                onClick={() => { ask(m.id); setQ('') }}
              >
                {m.name}
              </button>
            ))}
            {why && (
              <Callout tone="navy" title={graph.find(n => n.id === why.concept_id)?.name}>
                {why.text}
                <div className="text-[11px] text-muted mt-1">
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
