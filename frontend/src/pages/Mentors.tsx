import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Callout, DemoBadge, FlagChip, LevelChip, SectionTitle, Spinner } from '../components/ui'
import { apiC05 } from '../api_ext/C05'
import GuardianAsk from '../components/GuardianAsk'
import { refreshNotifications, useNotifications } from '../hooks/useNotifications'
import { CasePrep } from '../components/CasePrep'
import { CaseSummary } from '../components/CaseSummary'
import { useCaseSync } from '../hooks/useCaseSync'
import { useApp } from '../store'

const TIER: Record<string, { label: string; tone: string; bg: string; desc: string }> = {
  skill_mentor: { label: 'Skill Mentor', tone: '#0f5d5d', bg: '#e3f2f1', desc: 'Working developers and senior students — technical cases' },
  margdarshak: { label: 'Margdarshak', tone: '#9a4f0a', bg: '#fdf3e9', desc: 'Experienced & retired professionals — career and guidance' },
  safeguarding: { label: 'Safeguarding lead', tone: '#16324f', bg: '#e8eef5', desc: 'Trained staff for concerns about wellbeing or conduct' },
}
const STATUS: Record<string, string> = { open: 'Queued', matched: 'Matched', accepted: 'Accepted', scheduled: 'Scheduled', held: 'Session held', followup: 'Follow-up due', closed: 'Closed', awaiting_consent: 'Needs guardian approval', escalated: 'Safeguarding notified' }

export default function Mentors() {
  const { caseId } = useParams()
  return caseId ? <CaseDetail id={caseId} /> : <Overview />
}

function Overview() {
  const { me, version, toast, bump, refreshMe } = useApp()
  const nav = useNavigate()
  const [mentors, setMentors] = useState<any | null>(null)
  const [cases, setCases] = useState<any | null>(null)
  const [consent, setConsent] = useState<any | null>(null)
  const [concepts, setConcepts] = useState<any[]>([])
  const [form, setForm] = useState({ category: 'technical', concept_id: 'sql_outer_join', note: '', share: false })
  const [busy, setBusy] = useState(false)
  const notif = useNotifications()

  useEffect(() => {
    api.mentors().then(setMentors); api.cases().then(setCases); api.consent().then(setConsent)
    api.graph().then(g => setConcepts(g.nodes))
  }, [version])

  async function open(payload?: any) {
    setBusy(true)
    try {
      const p = payload ?? { category: form.category, concept_id: form.category === 'technical' ? form.concept_id : undefined, reason: form.note || (form.category === 'career' ? 'Career guidance' : 'Need help with this concept'), note: form.note, share_transcript: form.share }
      const c = await api.createCase(p)
      if (c.helpline) { toast('A safeguarding lead has been notified. You are not alone.', 'warn') }
      bump(); nav('/mentors/' + c.case_id)
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  if (!mentors || !cases || !consent) return <div className="py-16 flex justify-center"><Spinner /></div>
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div><div className="eyebrow">Human layer</div><h1 className="h-page">Chhatrachhaya <span className="text-muted font-semibold text-lg">· छत्रछाया</span></h1>
          <p className="text-muted mt-1 max-w-3xl">When SAARTHI can't move you forward, a person steps in — with a complete case report, so you never start from zero. Technical problems go to a <b>Skill Mentor</b>; career and guidance questions go to a <b>Margdarshak</b>.</p></div>
        {!mentors.mock && <Link to="/mentor-apply" className="btn btn-ghost btn-sm">Become a mentor</Link>}
        {mentors.mock && <DemoBadge label="demo mentors" title="Mentor profiles, verification and replies are mock data for now. Matching, routing and case reports are real." />}
      </div>

      {me?.is_minor && (
        <Callout tone={consent.scopes.mentor_sessions === 'granted' ? 'teal' : 'saffron'} title={consent.scopes.mentor_sessions === 'granted' ? 'Guardian approval recorded' : 'Guardian approval needed for mentor sessions'}>
          Because you're under 18, mentor sessions only happen inside SAARTHI, are logged, and need a parent or guardian's OK.
          {consent.scopes.mentor_sessions !== 'granted' && !consent.mock && <GuardianAsk consent={consent} onChange={() => { bump(); refreshMe() }} />}
          {consent.scopes.mentor_sessions !== 'granted' && consent.mock && (
            <div className="mt-2"><button className="btn btn-primary btn-sm" onClick={async () => { await api.consentDemo(); toast('Demo guardian approval recorded.'); bump(); refreshMe() }}>Demo: approve as guardian</button> <DemoBadge label="mock consent" /></div>
          )}
        </Callout>
      )}

      {cases.suggestions.length > 0 && cases.suggestions.map((s: any, i: number) => (
        <Callout key={i} tone="navy" title="SAARTHI suggests a mentor" icon="🤝">{s.reason}
          <div className="mt-2"><button className="btn btn-primary btn-sm" disabled={busy} onClick={() => open({ category: s.category, concept_id: s.concept_id, reason: s.reason, trigger: s.trigger })}>Open a case with the full report</button></div></Callout>
      ))}

      <div className="grid lg:grid-cols-[1fr_380px] gap-5">
        <div className="space-y-5 min-w-0">
          <div className="card p-5">
            <SectionTitle eyebrow="Your cases" title="Open and past" />
            {cases.cases.length === 0 && <div className="text-sm text-muted">No cases yet.</div>}
            <div className="space-y-2">{cases.cases.map((c: any) => (
              <Link key={c.id} to={'/mentors/' + c.id} className="block rounded-xl border border-line hover:bg-paper px-4 py-3">
                <div className="flex items-center gap-2 flex-wrap"><b className="text-navy">{c.concept_name ?? 'Career guidance'}</b>{notif.cases[c.id] > 0 && <span className="chip" style={{ background: '#e07a1f', color: '#fff' }}>{notif.cases[c.id]} new</span>}<span className="chip" style={{ background: TIER[c.tier]?.bg, color: TIER[c.tier]?.tone }}>{TIER[c.tier]?.label ?? c.tier}</span><span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{STATUS[c.status] ?? c.status}</span></div>
                <div className="text-xs text-muted mt-0.5">{c.mentor ? `with ${c.mentor.name}${c.mentor.is_mock ? ' (demo)' : ''}` : 'waiting for a match'} · {c.created_at.replace('T', ' ')}</div>
              </Link>))}</div>
          </div>

          <div className="card p-5">
            <SectionTitle eyebrow="Meet the mentors" title="Verified Chhatrachhaya mentors" />
            <div className="grid sm:grid-cols-2 gap-3">{mentors.mentors.map((m: any) => (
              <div key={m.id} className="rounded-xl border border-line p-3.5">
                <div className="flex items-center gap-2 flex-wrap"><b className="text-navy">{m.name}</b><span className="chip" style={{ background: TIER[m.tier].bg, color: TIER[m.tier].tone }}>{TIER[m.tier].label}</span></div>
                <div className="text-xs text-muted mt-0.5">{m.headline}</div>
                <p className="text-sm mt-1.5">{m.bio}</p>
                <div className="flex flex-wrap gap-1 mt-2">{m.languages.map((l: string) => <span key={l} className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{l}</span>)}<span className="chip" style={{ background: '#e2f4ea', color: '#1f6f45' }}>✓ {m.verification_status}{m.is_mock ? ' (demo)' : ''}</span></div>
              </div>))}</div>
            <p className="text-xs text-muted mt-3">Mentors are matched by a transparent score (expertise, language, availability, workload) — you don't browse and message strangers. Personal contact details can't be shared in a case.</p>
          </div>
        </div>

        <aside className="card p-5 h-fit space-y-3 lg:sticky lg:top-20">
          <SectionTitle eyebrow="Ask for a human" title="Open a case" />
          <div className="grid grid-cols-2 gap-2">{(['technical', 'career'] as const).map(k => <button key={k} onClick={() => setForm(f => ({ ...f, category: k }))} className={`rounded-xl border p-3 text-left text-sm ${form.category === k ? 'border-saffron bg-saffron-soft ring-2 ring-saffron/30' : 'border-line'}`}><b className="text-navy block">{k === 'technical' ? 'A technical problem' : 'Career guidance'}</b><span className="text-xs text-muted">{TIER[k === 'technical' ? 'skill_mentor' : 'margdarshak'].label}</span></button>)}</div>
          {form.category === 'technical' && <label className="block text-sm font-semibold">Concept<select className="input mt-1" value={form.concept_id} onChange={e => setForm(f => ({ ...f, concept_id: e.target.value }))}>{concepts.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}
          <label className="block text-sm font-semibold">What would you like help with?<textarea className="input mt-1 min-h-[90px]" value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} placeholder={form.category === 'career' ? 'e.g. How do I prepare for my first interview?' : 'e.g. My LEFT JOIN keeps dropping customers'} /></label>
          <label className="flex items-start gap-2 text-xs text-muted"><input type="checkbox" className="mt-0.5" checked={form.share} disabled={consent.scopes.transcript_share !== 'granted'} onChange={e => setForm(f => ({ ...f, share: e.target.checked }))} /><span>Share short excerpts of my last conversation with the mentor. {consent.scopes.transcript_share !== 'granted' && !me?.is_minor && <button className="underline font-semibold" onClick={async () => { await api.consentSelf('transcript_share'); bump() }}>Allow this</button>}</span></label>
          <button className="btn btn-saffron w-full" disabled={busy} onClick={() => open()}>{busy ? 'Opening…' : 'Open case'}</button>
          <div className="text-xs text-muted">If you're struggling with how you feel, say so here — a trained safeguarding lead, not a regular mentor, will respond. India: Tele-MANAS <b>14416</b>.</div>
        </aside>
      </div>
    </div>
  )
}

function CaseDetail({ id }: { id: string }) {
  const { toast, bump, setRoadmapNote } = useApp()
  const [c, setC] = useState<any | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [rep, setRep] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const isNearBottomRef = useRef(true)

  const load = () => api.caseDetail(id).then(setC).catch(e => toast(e.message, 'err'))
  useEffect(() => { load() /* eslint-disable-next-line */ }, [id])
  useEffect(() => { if (c) apiC05.caseRead(id).then(refreshNotifications).catch(() => {}) }, [id, c?.messages?.length])

  const handleChatScroll = () => {
    if (!chatScrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = chatScrollRef.current
    isNearBottomRef.current = scrollHeight - scrollTop - clientHeight < 50
  }

  const { announcement } = useCaseSync(id, {
    active: c ? ['open', 'matched', 'accepted', 'scheduled', 'held'].includes(c.status) : true,
    role: 'learner',
    otherPartyName: c?.mentor?.name || 'your mentor',
    onStatus: (newStatus) => {
      setC((prev: any) => prev ? { ...prev, status: newStatus } : prev)
      api.caseDetail(id).then(setC).catch(() => {})
    },
    onMessages: (newMsgs) => {
      setC((prev: any) => {
        if (!prev) return prev
        const existing = prev.messages || []
        const map = new Map<string, any>()
        existing.forEach((m: any) => map.set(m.id, m))
        newMsgs.forEach((m: any) => map.set(m.id, m))
        return { ...prev, messages: Array.from(map.values()) }
      })
      if (isNearBottomRef.current) {
        setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth' }), 50)
      }
    },
  })

  async function send() {
    if (!text.trim()) return
    const msgText = text
    const tempId = `temp-${Date.now()}`
    const optimisticMsg = {
      id: tempId,
      sender: 'learner',
      text: msgText,
      sending: true,
      at: 'just now',
      created_at: new Date().toISOString(),
    }
    setText('')
    setC((prev: any) => prev ? { ...prev, messages: [...(prev.messages || []), optimisticMsg] } : prev)
    setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    setBusy(true)
    try {
      const r = await api.sendMsg(id, msgText)
      if (r.blocked) {
        toast(r.reason, 'warn')
        setC((prev: any) => prev ? { ...prev, messages: (prev.messages || []).filter((m: any) => m.id !== tempId) } : prev)
      } else {
        setC(r.case)
      }
    } catch (e: any) {
      toast(e.message, 'err')
      setC((prev: any) => prev ? { ...prev, messages: (prev.messages || []).filter((m: any) => m.id !== tempId) } : prev)
    } finally {
      setBusy(false)
    }
  }

  async function simulate() {
    try { const r = await api.simulateSession(id, 0.8); setC(r.case); if (r.after?.roadmap?.changed) setRoadmapNote(r.after.roadmap.change_reason); bump(); toast('Demo session recorded as mentor evidence.') } catch (e: any) { toast(e.message, 'err') }
  }
  async function followup() { try { const r = await api.followup(id); setC(r.case); bump() } catch (e: any) { toast(e.message, 'err') } }

  if (!c) return <div className="py-16 flex justify-center"><Spinner /></div>
  const r = c.report ?? {}
  const t = TIER[c.tier] ?? TIER.skill_mentor
  const mock = c.mentor?.is_mock
  return (
    <div className="space-y-5">
      {announcement && <div className="sr-only" aria-live="polite">{announcement}</div>}
      <Link to="/mentors" className="text-sm font-bold text-teal">← All cases</Link>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div><div className="eyebrow">Mentor case</div><h1 className="h-page">{c.concept_name ?? 'Career guidance'}</h1>
          <div className="flex items-center gap-2 flex-wrap mt-1.5"><span className="chip" style={{ background: t.bg, color: t.tone }}>{t.label}</span><span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{STATUS[c.status] ?? c.status}</span>{c.is_mock && <DemoBadge label="demo mentor" />}</div></div>
        <button className="btn btn-ghost btn-sm" onClick={() => setRep(true)}>Report a concern</button>
      </div>

      {c.status === 'escalated' && <Callout tone="navy" title="A safeguarding lead has been notified" icon="🛟">{r.note} If you feel unsafe right now, call <b>14416</b> (Tele-MANAS, free, 24×7) or a trusted adult.</Callout>}
      {c.status === 'awaiting_consent' && <Callout tone="saffron" title="Waiting for guardian approval">A parent or guardian needs to approve mentor sessions before we match you. <Link to="/mentors" className="underline font-bold">Go back to approve (demo)</Link></Callout>}
      {c.status === 'closed' && c.followup && <Callout tone={c.followup.improved ? 'teal' : 'saffron'} title="Follow-up result">Your estimate on this concept went from {Math.round(c.followup.p_at_open * 100)}% to <b>{Math.round(c.followup.p_now * 100)}%</b> ({c.followup.gain >= 0 ? '+' : ''}{Math.round(c.followup.gain * 100)} points). {c.followup.improved ? 'The session helped.' : 'Not enough movement yet — keep practising or request another session.'}</Callout>}

      <CasePrep caseId={id} status={c.status} />
      <CaseSummary caseId={id} status={c.status} />

      <div className="grid lg:grid-cols-[1fr_380px] gap-5">
        <div className="space-y-4 min-w-0">
          {c.mentor && (
            <div className="card p-4"><div className="flex items-center gap-2 flex-wrap"><b className="text-navy text-lg">{c.mentor.name}</b><span className="chip" style={{ background: TIER[c.mentor.tier].bg, color: TIER[c.mentor.tier].tone }}>{TIER[c.mentor.tier].label}</span><span className="chip" style={{ background: '#e2f4ea', color: '#1f6f45' }}>✓ verified{mock ? ' (demo)' : ''}</span></div>
              <div className="text-sm text-muted">{c.mentor.headline}</div>
              <div className="text-sm mt-2"><b>Why this mentor:</b> {c.match_reasons.join(' · ')}</div>
              {c.scheduled_for && <div className="text-sm mt-1"><b>First slot:</b> {c.scheduled_for}</div>}</div>
          )}
          <div className="card p-4 flex flex-col" style={{ minHeight: 320 }}>
            <div className="eyebrow mb-2">Case conversation <span className="normal-case font-semibold text-muted">· inside SAARTHI only · contact details are blocked</span></div>
            <div ref={chatScrollRef} onScroll={handleChatScroll} className="flex-1 space-y-2 overflow-auto max-h-[380px] pr-1" aria-live="polite">
              {c.messages.map((m: any) => (
                <div key={m.id} translate={m.sender === 'system' ? undefined : 'no'} className={`text-sm rounded-2xl px-3.5 py-2 max-w-[88%] ${m.sender === 'learner' ? 'bg-navy text-white ml-auto' : m.sender === 'mentor' ? 'bg-teal-soft' : 'bg-paper text-muted italic text-xs'}`}>
                  {m.sender === 'mentor' && <div className="text-[11px] font-extrabold text-teal mb-0.5">{c.mentor?.name}{m.is_mock ? ' · demo reply' : ''}</div>}
                  {m.text}
                  {m.sending && <span className="text-[11px] opacity-70 ml-1.5 italic">(sending…)</span>}
                </div>))}
              <div ref={end} />
            </div>
            {['accepted', 'scheduled', 'held', 'matched'].includes(c.status) && (
              <div className="flex gap-2 mt-3"><input className="input" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Message your mentor…" aria-label="Message" /><button className="btn btn-primary" disabled={busy} onClick={send}>Send</button></div>
            )}
          </div>
          <div className="flex gap-2 flex-wrap">
            {c.mentor?.is_mock && ['accepted', 'scheduled', 'matched', 'held'].includes(c.status) && <button className="btn btn-saffron" onClick={simulate}>Demo: simulate the session happening</button>}
            {c.status === 'followup' && <button className="btn btn-primary" onClick={followup}>Run the follow-up check</button>}
          </div>
        </div>

        <aside className="card p-4 space-y-3 h-fit">
          <div className="eyebrow">Case report your mentor sees</div>
          {r.concept && <div className="rounded-xl bg-paper p-3 text-sm"><b>{r.concept.name}</b> · <LevelChip level={r.concept.level} /> {Math.round(r.concept.p * 100)}% {r.concept.flags?.map((f: string) => <FlagChip key={f} flag={f} />)}</div>}
          <Row k="Goal" v={r.learner?.goal} /><Row k="Language" v={r.learner?.language} /><Row k="Why now" v={r.reason} />
          {r.misconceptions?.length > 0 && <div><div className="text-xs font-bold text-muted">Misconceptions</div>{r.misconceptions.map((m: any, i: number) => <div key={i} className="text-sm"><FlagChip flag="misconception" /> {m.name} <span className="text-muted text-xs">({m.status}, {m.cycles} cycles)</span>{m.learner_statement && <div className="text-xs italic text-muted">“{m.learner_statement}”</div>}</div>)}</div>}
          {r.strategies_tried?.length > 0 && <div><div className="text-xs font-bold text-muted">Strategies already tried</div><div className="flex flex-wrap gap-1 mt-1">{r.strategies_tried.map((s: any, i: number) => <span key={i} className="chip" style={{ background: '#eceff3', color: '#16324f' }}>{s.strategy.replace('_', ' ')}{s.gain !== null && s.gain !== undefined ? ` (${s.gain >= 0 ? '+' : ''}${Math.round(s.gain * 100)})` : ''}</span>)}</div></div>}
          {r.evidence_timeline?.length > 0 && <div><div className="text-xs font-bold text-muted">Recent evidence</div><ul className="text-xs mt-1 space-y-0.5">{r.evidence_timeline.map((e: any, i: number) => <li key={i}>{e.at.slice(5).replace('T', ' ')} · {e.source.replace('_', ' ')} · {e.correct === null ? '—' : e.correct ? '✓' : '✗'}</li>)}</ul></div>}
          {r.prerequisite_state?.length > 0 && <div><div className="text-xs font-bold text-muted">Prerequisites</div><div className="text-xs">{r.prerequisite_state.map((p: any) => `${p.concept}: ${p.level}`).join(' · ')}</div></div>}
          {r.suggested_intervention?.length > 0 && <Callout tone="teal" title="Suggested intervention">{r.suggested_intervention[0]}</Callout>}
          {r.transcript_excerpts && <div><div className="text-xs font-bold text-muted">Shared conversation excerpts</div>{r.transcript_excerpts.map((t: any, i: number) => <div key={i} className="text-xs"><b>{t.role}:</b> {t.text}</div>)}</div>}
          {c.outcome && <Callout tone="navy" title="Mentor outcome">{c.outcome.notes}<div className="mt-1 font-semibold">Next: {c.outcome.next_step}</div></Callout>}
          <div className="text-[11px] text-muted">Only what's listed here is shared. Mentors cannot change your mastery directly — their input is recorded as evidence with its own weight.</div>
        </aside>
      </div>

      {rep && <ReportModal caseId={id} onClose={() => setRep(false)} />}
    </div>
  )
}

function Row({ k, v }: { k: string; v?: string }) { return v ? <div className="text-sm"><span className="text-xs font-bold text-muted block">{k}</span>{v}</div> : null }

function ReportModal({ caseId, onClose }: { caseId: string; onClose: () => void }) {
  const { toast } = useApp()
  const [d, setD] = useState('')
  return (
    <div className="fixed inset-0 z-[70] bg-navy/50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Report a concern">
      <div className="bg-white rounded-2xl p-5 w-full max-w-md space-y-3">
        <h2 className="font-extrabold text-navy text-lg">Report a concern</h2>
        <p className="text-sm text-muted">A safeguarding lead reviews every report (target: within 24 hours). You can also block the mentor from your case.</p>
        <textarea className="input min-h-[100px]" value={d} onChange={e => setD(e.target.value)} placeholder="What happened?" />
        <div className="flex gap-2 justify-end"><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={async () => { try { const r = await api.report({ case_id: caseId, detail: d, category: 'concern' }); toast(r.message); onClose() } catch (e: any) { toast(e.message, 'err') } }}>Send report</button></div>
      </div>
    </div>
  )
}
