import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../api'
import WebResources from '../components/WebResources'
import { SpeakButton } from '../components/audio'
import ExplainBack from '../components/ExplainBack'
import FeedbackButtons from '../components/FeedbackButtons'
import JoinDiagram from '../components/JoinDiagram'
import QuizRunner from '../components/QuizRunner'
import SqlWorkbench from '../components/SqlWorkbench'
import { Bar, Callout, Collapsible, FlagChip, LevelChip, SectionTitle, Spinner } from '../components/ui'
import { useApp } from '../store'

const STRATS: [string, string][] = [['analogy', 'Analogy'], ['worked_example', 'Worked example'], ['contrasting_cases', 'Contrasting cases'], ['code_tracing', 'Code tracing'], ['practice_first', 'Practice first'], ['text', 'Plain']]

export default function Learn() {
  const { conceptId = '' } = useParams()
  const loc = useLocation()
  const { version, openVoice, openStuck, toast, bump } = useApp()
  const [c, setC] = useState<any | null>(null)
  const [ex, setEx] = useState<any | null>(null)
  const [exBusy, setExBusy] = useState(false)
  const [task, setTask] = useState<any | null>(null)
  const [quiz, setQuiz] = useState(false)
  const [plans, setPlans] = useState<Record<string, any>>({})
  const [challengeItem, setChallengeItem] = useState<any | null>(null)
  const [prereqProbe, setPrereqProbe] = useState<any | null>(null)
  const [vakhChallenge, setVakhChallenge] = useState<any | null>(null)

  useEffect(() => { setC(null); setEx(null); setTask(null); setQuiz(false); setVakhChallenge(null); window.scrollTo(0, 0) }, [conceptId])
  useEffect(() => { 
    api.concept(conceptId).then(r => { setC(r); setTask((t: any) => t ?? r.tasks[0] ?? null) }).catch(e => toast(e.message, 'err'))
    api.vakhChallenge(conceptId).then(r => setVakhChallenge(r?.challenge ?? (r?.title ? r : null))).catch(() => setVakhChallenge(null))
  }, [conceptId, version, toast])
  useEffect(() => { if (loc.hash === '#teachback') setTimeout(() => document.getElementById('teachback')?.scrollIntoView({ behavior: 'smooth' }), 400) }, [loc.hash, c?.concept?.id])

  async function explain(strategy?: string, misconception_id?: string) {
    setExBusy(true)
    try { setEx(await api.teach({ concept_id: conceptId, strategy, misconception_id })); bump() } catch (e: any) { toast(e.message, 'err') } finally { setExBusy(false) }
  }
  useEffect(() => { if (c && !ex) explain() /* eslint-disable-next-line */ }, [c?.concept?.id])

  async function loadPlan(id: string) { if (!plans[id]) setPlans(p => ({ ...p, [id]: 'loading' })); setPlans(p => ({ ...p })); const r = await api.misPlan(id); setPlans(p => ({ ...p, [id]: r })) }

  function handleFeedbackAction(action: any) {
    if (action.type === 'strategy' && action.explanation) {
      setEx(action.explanation)
    }
    if (action.type === 'probe' && action.item) {
      setChallengeItem(action.item)
    }
    if (action.prereq_probe) {
      setPrereqProbe(action.prereq_probe)
    }
  }

  async function handleLaunchVakh() {
    try {
      const res = await api.vakhLaunch(conceptId)
      if (res.launch_url) {
        window.open(res.launch_url, '_blank', 'noopener,noreferrer')
      } else {
        toast(res.message || 'Vakh is not connected yet.', 'err')
      }
    } catch (e: any) {
      toast(e.message || 'Unable to launch Vakh challenge', 'err')
    }
  }

  if (!c) return <div className="py-16 flex justify-center"><Spinner label="Opening concept…" /></div>
  const st = c.state
  const activeMis = (st.misconceptions ?? []) as string[]

  return (
    <div className="grid lg:grid-cols-[1fr_320px] gap-5">
      <div className="space-y-5 min-w-0">
        <div>
          <div className="eyebrow">{c.concept.domain} · about {c.concept.minutes} min</div>
          <h1 className="h-page">{c.concept.name}</h1>
          <div className="flex items-center gap-2 flex-wrap mt-2">
            <LevelChip level={st.level} />{st.flags.map((f: string) => <FlagChip key={f} flag={f} />)}
            <span className="text-sm text-muted font-semibold">{Math.round(st.p * 100)}% · confidence {Math.round(st.confidence * 100)}%</span>
          </div>
        </div>

        {challengeItem && (
          <div className="card p-5 border-saffron bg-[#fffaf5] space-y-3" id="t03-challenge-card">
            <SectionTitle eyebrow="Too easy challenge" title="Prove it: solve this harder question" right={<button className="btn btn-ghost btn-xs" onClick={() => setChallengeItem(null)}>Dismiss</button>} />
            <QuizRunner total={1} fixedItems={[challengeItem]} title="Challenge" onFinish={() => { toast('Challenge completed!'); setChallengeItem(null) }} />
          </div>
        )}

        {prereqProbe && (
          <Callout tone="saffron" title={`Foundational check: ${prereqProbe.concept_name}`}>
            <div className="flex items-center justify-between gap-2 flex-wrap text-sm">
              <span>You indicated this was difficult. Checking this prerequisite concept will help you progress.</span>
              <div className="flex gap-2">
                <Link to={'/learn/' + prereqProbe.concept_id} className="btn btn-xs btn-primary">Review {prereqProbe.concept_name}</Link>
                <button className="btn btn-xs btn-ghost" onClick={() => setPrereqProbe(null)}>Dismiss</button>
              </div>
            </div>
          </Callout>
        )}

        {st.flags.includes('blocked') && (
          <Callout tone="saffron" title="This builds on something that's still shaky">
            {st.blocked_by.map((p: string) => <Link key={p} to={'/learn/' + p} className="underline font-bold mr-2">{p.replace(/_/g, ' ')}</Link>)}
            <span>— fix those first and this will get easier.</span>
          </Callout>
        )}

        <section className="card p-5 space-y-3">
          <SectionTitle eyebrow="1 · Learn" title="Explanation" right={ex && <SpeakButton text={ex.text} label="Read aloud" />} />
          {exBusy && !ex && <Spinner label="Choosing how to teach this to you…" />}
          {ex && (
            <div className="space-y-3 pop">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="chip" style={{ background: '#e3f2f1', color: '#0f5d5d' }}>Approach: {ex.strategy_label}</span>
                <span className="text-xs text-muted">{ex.why_strategy}</span>
              </div>
              <div className="whitespace-pre-wrap text-[0.95rem] leading-relaxed">{ex.text}</div>
              {ex.key_points?.length > 0 && <ul className="list-disc pl-5 text-sm space-y-0.5">{ex.key_points.map((k: string, i: number) => <li key={i}>{k}</li>)}</ul>}
              <div className="flex gap-1.5 flex-wrap items-center pt-1">
                <span className="text-xs font-bold text-muted mr-1">Not clicking? Try another way:</span>
                {STRATS.filter(([id]) => ex.strategy !== id).map(([id, label]) => <button key={id} className="btn btn-ghost btn-sm" disabled={exBusy} onClick={() => explain(id)}>{label}</button>)}
              </div>
              <div className="pt-2 border-t border-line">
                <FeedbackButtons conceptId={conceptId} context="explanation" onAction={handleFeedbackAction} />
              </div>
            </div>
          )}
        </section>

        {(ex?.visual === 'join_diagram' || c.note?.visual === 'join_diagram') && <JoinDiagram initial={activeMis.includes('left_join_where_filter') ? 'left_where' : 'left'} />}

        {c.tasks.length > 0 && (
          <section className="card p-5 space-y-3">
            <SectionTitle eyebrow="2 · Practise" title="Write the SQL" right={<span className="text-xs text-muted">Checked by running your query, not by guessing</span>} />
            <div className="flex gap-1.5 flex-wrap">
              {c.tasks.map((t: any, i: number) => <button key={t.id} onClick={() => setTask(t)} className={`btn btn-sm ${task?.id === t.id ? 'btn-primary' : 'btn-ghost'}`}>Task {i + 1}</button>)}
            </div>
            <SqlWorkbench task={task} />
            <div className="pt-2 border-t border-line">
              <FeedbackButtons conceptId={conceptId} context="task" itemId={task?.id} onAction={handleFeedbackAction} />
            </div>
          </section>
        )}

        <section className="card p-5 space-y-3">
          <SectionTitle eyebrow={c.tasks.length ? '3 · Check' : '2 · Check'} title="Quick check" />
          {!quiz ? <div className="flex items-center gap-3 flex-wrap"><span className="text-sm text-muted">Three questions on this concept. Rate how sure you are first.</span><button className="btn btn-primary" onClick={() => setQuiz(true)}>Start quick check</button></div> :
            <QuizRunner total={Math.min(3, c.n_items)} conceptId={conceptId} title="Check" onFinish={() => { toast('Check done — your estimate is updated.'); setQuiz(false) }} />}
          <div className="pt-2 border-t border-line">
            <FeedbackButtons conceptId={conceptId} context="quiz" onAction={handleFeedbackAction} />
          </div>
        </section>

        <WebResources conceptId={conceptId} />

        {vakhChallenge && (
          <section className="card p-5 bg-gradient-to-r from-purple-50/70 to-white border-2 border-purple-200 space-y-3 shadow-sm">
            <SectionTitle
              eyebrow="Practical Challenge · Build with Vakh"
              title={vakhChallenge.title}
              right={
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-800 font-bold uppercase tracking-wider">
                  Verified Work Product
                </span>
              }
            />
            <p className="text-sm text-slate-700 leading-relaxed">
              {vakhChallenge.description}
            </p>
            {vakhChallenge.requirements && vakhChallenge.requirements.length > 0 && (
              <div className="space-y-1 bg-white p-3 rounded-xl border border-purple-100">
                <span className="text-xs font-bold text-navy">Challenge Requirements:</span>
                <ul className="list-disc pl-5 text-xs text-slate-600 space-y-1 mt-1">
                  {vakhChallenge.requirements.map((req: string, idx: number) => (
                    <li key={idx}>{req}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="pt-2 flex items-center justify-between gap-3 flex-wrap border-t border-purple-100">
              <span className="text-xs text-muted">
                When your submission is reviewed on Vakh, the review counts as evidence and your learning map updates.
              </span>
              <button
                onClick={handleLaunchVakh}
                className="btn btn-primary text-xs py-2 px-4 bg-purple-700 hover:bg-purple-800 text-white font-bold flex items-center gap-1.5 shadow"
              >
                <span>🚀 Open Challenge on Vakh</span>
              </button>
            </div>
          </section>
        )}

        <section id="teachback" className="space-y-3 scroll-mt-20">
          {c.has_rubric ? <ExplainBack conceptId={conceptId} /> :
            <div className="card p-5 text-sm text-muted"><b className="text-navy">Teach it back</b> isn't available for this concept yet — the quick check and practice above still update your estimate.</div>}
        </section>

        {c.misconceptions_known.length > 0 && (
          <section className="card p-5 space-y-2">
            <SectionTitle eyebrow="Common mix-ups" title="Watch out for these" />
            {c.misconceptions_known.map((m: any) => (
              <div key={m.id} className={`rounded-xl border p-3 ${activeMis.includes(m.id) ? 'border-violet bg-[#fbf6fd]' : 'border-line'}`}>
                <div className="flex items-center gap-2 flex-wrap"><b className="text-navy">{m.name}</b>{activeMis.includes(m.id) && <FlagChip flag="misconception" />}
                  <button className="btn btn-ghost btn-sm ml-auto" onClick={() => explain('contrasting_cases', m.id)}>Show me with contrasting cases</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => loadPlan(m.id)}>How is it fixed?</button></div>
                {plans[m.id] && plans[m.id] !== 'loading' && (
                  <ol className="list-decimal pl-5 mt-2 text-sm space-y-1">{plans[m.id].steps.map((s: any, i: number) => <li key={i}>{s.text ?? (s.task_ids?.length ? `Practise with task(s) above (${s.task_ids.length})` : '')}{s.query && <pre className="text-[11.5px] bg-navy text-white rounded-lg p-2 mt-1 overflow-auto whitespace-pre-wrap">{s.query}</pre>}</li>)}</ol>
                )}
              </div>
            ))}
          </section>
        )}
      </div>

      <aside className="space-y-4 lg:sticky lg:top-20 h-fit">
        <div className="card p-4 space-y-2">
          <div className="eyebrow">Your estimate</div>
          <div className="text-3xl font-extrabold text-navy">{Math.round(st.p * 100)}%</div>
          <Bar value={st.p} />
          <div className="text-xs text-muted">{st.n_evidence} piece(s) of evidence · {st.source_types.join(', ') || 'none yet'}</div>
          <button className="btn btn-ghost btn-sm w-full" onClick={async () => { try { const r = await api.dispute({ concept_id: conceptId, kind: 'dispute_level', note: 'learner thinks the estimate is wrong' }); toast(r.message); bump() } catch (e: any) { toast(e.message, 'err') } }}>This estimate looks wrong</button>
        </div>
        <div className="card p-4 space-y-2">
          <button className="btn btn-saffron w-full" onClick={() => openVoice('explain_back', conceptId)}>🎙 Talk about this</button>
          <button className="btn btn-ghost w-full" onClick={() => openStuck({ concept_id: conceptId })}>I'm stuck on this</button>
        </div>
        {c.concept.prereqs.length > 0 && (
          <div className="card p-4">
            <div className="eyebrow">Builds on</div>
            <ul className="mt-1.5 space-y-1">{c.concept.prereqs.map((p: any) => <li key={p.id}><Link to={'/learn/' + p.id} className="text-sm font-bold text-teal hover:underline">{p.name}</Link></li>)}</ul>
          </div>
        )}
      </aside>
    </div>
  )
}
