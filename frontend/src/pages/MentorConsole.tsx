import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiC02 } from '../api_ext/C02'
import { apiC05 } from '../api_ext/C05'
import { refreshNotifications, useNotifications } from '../hooks/useNotifications'
import CaseReport from '../components/CaseReport'
import { Callout, SectionTitle, Spinner } from '../components/ui'
import { useCaseSync } from '../hooks/useCaseSync'
import { useApp } from '../store'

const GROUPS: [string, string][] = [['new', 'New'], ['active', 'Active'], ['followup', 'Follow-up'], ['closed', 'Closed']]
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const SCALE = ['1 · Not yet', '2 · A little', '3 · Partly', '4 · Mostly', '5 · Clearly']
const STATUS: Record<string, string> = { matched: 'New — waiting for you', accepted: 'Accepted', scheduled: 'Scheduled', held: 'Session held', followup: 'Follow-up due', closed: 'Closed' }

function errText(e: any): string {
  try { const j = JSON.parse(e.message); return j.message ?? e.message } catch { return e.message }
}

export default function MentorConsole() {
  const { caseId } = useParams()
  return caseId ? <CaseView id={caseId} /> : <Overview />
}

function Overview() {
  const { toast } = useApp()
  const [me, setMe] = useState<any | null>(null)
  const [group, setGroup] = useState('new')
  const [cases, setCases] = useState<any[] | null>(null)
  const [denied, setDenied] = useState(false)
  const [agree, setAgree] = useState(false)
  const [slots, setSlots] = useState<string[]>([])
  const [slot, setSlot] = useState({ day: 'Mon', time: '18:00' })
  const notif = useNotifications()

  const load = () => apiC02.me().then(m => { setMe(m); setSlots(m.mentor.availability) }).catch((e: any) => { if ([403, 404].includes(e.status)) setDenied(true); else toast(errText(e), 'err') })
  useEffect(() => { load() /* eslint-disable-next-line */ }, [])
  useEffect(() => { if (me) apiC02.cases(group).then(r => setCases(r.cases)).catch((e: any) => toast(errText(e), 'err')) /* eslint-disable-next-line */ }, [group, me?.counts])

  if (denied) return <div className="max-w-xl mx-auto"><Callout tone="navy" title="Not available">The mentor console is for verified mentors, and only when real mentors are switched on.</Callout></div>
  if (!me) return <div className="py-16 flex justify-center"><Spinner /></div>

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div><div className="eyebrow">Mentor console{me.mentor.is_demo ? ' · demo mentor' : ''}</div><h1 className="h-page">{me.mentor.name}</h1>
          <p className="text-muted mt-1">Open cases {me.load} of {me.mentor.active_case_cap}. You only ever see the case report SAARTHI prepared — a learner's first name and age group, never contact details.</p></div>
      </div>
      {!me.pledge.current && (
        <Callout tone="saffron" title="The code of conduct was updated">
          <ul className="list-disc pl-5 text-sm space-y-1">{me.pledge.promises.map((p: any) => <li key={p.id}>{p.en}</li>)}</ul>
          <label className="flex items-center gap-2 mt-2 text-sm font-semibold"><input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} />I have read this and agree.</label>
          <button className="btn btn-primary btn-sm mt-2" disabled={!agree} onClick={async () => { try { await apiC02.acceptPledge(me.pledge.version); load() } catch (e: any) { toast(errText(e), 'err') } }}>Accept</button>
        </Callout>)}
      <div className="grid lg:grid-cols-[1fr_320px] gap-5">
        <section className="card p-5 min-w-0">
          <div className="flex gap-1.5 flex-wrap mb-3">{GROUPS.map(([g, l]) => <button key={g} onClick={() => setGroup(g)} className={`btn btn-sm ${group === g ? 'btn-primary' : 'btn-ghost'}`}>{l} <span className="opacity-70">{me.counts[g]}</span></button>)}</div>
          {!cases ? <Spinner /> : cases.length === 0 ? <div className="text-sm text-muted">Nothing here.</div> : (
            <div className="space-y-2">{cases.map(c => (
              <Link key={c.id} to={'/mentor-console/' + c.id} className="block rounded-xl border border-line hover:bg-paper px-4 py-3">
                <div className="flex items-center gap-2 flex-wrap"><b className="text-navy">{c.concept_name ?? 'Career guidance'}</b><span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{STATUS[c.status] ?? c.status}</span>{c.age_band === 'under_18' && <span className="chip" style={{ background: '#fdf3e9', color: '#9a4f0a' }}>under 18</span>}{notif.cases[c.id] > 0 && <span className="chip" style={{ background: '#e07a1f', color: '#fff' }}>{notif.cases[c.id]} new</span>}</div>
                <div className="text-xs text-muted">{c.learner_first_name} · {c.created_at.replace('T', ' ')}{c.scheduled_for ? ` · first session ${c.scheduled_for}` : ''}</div>
              </Link>))}</div>)}
        </section>
        <aside className="card p-5 h-fit space-y-3">
          <SectionTitle eyebrow="Availability" title="Your weekly slots (India time)" />
          <div className="flex flex-wrap gap-1.5">{slots.map(s => <button key={s} className="chip" style={{ background: '#e3f2f1', color: '#0f5d5d' }} onClick={() => setSlots(slots.filter(x => x !== s))}>{s} ✕</button>)}{slots.length === 0 && <span className="text-xs text-muted">None yet.</span>}</div>
          <div className="flex gap-2 items-center"><select className="input w-20" value={slot.day} onChange={e => setSlot({ ...slot, day: e.target.value })}>{DAYS.map(d => <option key={d}>{d}</option>)}</select><input className="input w-28" type="time" value={slot.time} onChange={e => setSlot({ ...slot, time: e.target.value })} />
            <button className="btn btn-ghost btn-sm" onClick={() => { const s = `${slot.day} ${slot.time}`; if (!slots.includes(s)) setSlots([...slots, s]) }}>Add</button></div>
          <button className="btn btn-primary btn-sm" onClick={async () => { try { await apiC02.setAvailability(slots); toast('Saved.'); load() } catch (e: any) { toast(errText(e), 'err') } }}>Save availability</button>
        </aside>
      </div>
    </div>
  )
}

function CaseView({ id }: { id: string }) {
  const { toast } = useApp()
  const nav = useNavigate()
  const [c, setC] = useState<any | null>(null)
  const [me, setMe] = useState<any | null>(null)
  const [text, setText] = useState('')
  const [slot, setSlot] = useState('')
  const [notes, setNotes] = useState('')
  const [next, setNext] = useState('')
  const [demo, setDemo] = useState(3)
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  const load = () => apiC02.caseDetail(id).then(setC).catch((e: any) => toast(errText(e), 'err'))
  useEffect(() => { load(); apiC02.me().then(setMe).catch(() => {}) /* eslint-disable-next-line */ }, [id])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [c?.messages?.length])
  useEffect(() => { if (c) apiC05.caseRead(id).then(refreshNotifications).catch(() => {}) }, [id, c?.messages?.length])

  useCaseSync(id, {
    active: c ? ['matched', 'accepted', 'scheduled', 'held'].includes(c.status) : true,
    role: 'mentor',
    otherPartyName: c?.report?.learner?.first_name || 'the learner',
    onStatus: (newStatus) => {
      setC((prev: any) => prev ? { ...prev, status: newStatus } : prev)
      apiC02.caseDetail(id).then(setC).catch(() => {})
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
    },
  })

  async function act(fn: () => Promise<any>, ok?: string, after?: () => void) {
    setBusy(true)
    try { const r = await fn(); if (ok) toast(ok); if (after) after(); else if (r && r.id) setC(r); else await load() } catch (e: any) { toast(errText(e), 'err') } finally { setBusy(false) }
  }

  if (!c) return <div className="py-16 flex justify-center"><Spinner /></div>
  const working = ['accepted', 'scheduled', 'held'].includes(c.status)
  const slots: string[] = me?.mentor?.availability ?? []

  return (
    <div className="space-y-5">
      <Link to="/mentor-console" className="text-sm font-bold text-teal">← All cases</Link>
      <div><div className="eyebrow">Case</div><h1 className="h-page">{c.concept_name ?? 'Career guidance'}</h1>
        <div className="mt-1.5"><span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{STATUS[c.status] ?? c.status}</span> {c.scheduled_for && <span className="text-sm text-muted ml-2">First session: {c.scheduled_for}</span>}</div></div>
      {c.status === 'matched' && (
        <Callout tone="navy" title="This case was matched to you">
          <div className="text-sm">{c.match_reasons.join(' · ')}</div>
          <div className="flex gap-2 flex-wrap mt-2 items-center">
            <select className="input w-auto" value={slot} onChange={e => setSlot(e.target.value)}><option value="">Choose a first slot…</option>{slots.map(s => <option key={s}>{s}</option>)}</select>
            <input className="input w-48" placeholder="…or write one (e.g. Sat 11:00)" value={slots.includes(slot) ? '' : slot} onChange={e => setSlot(e.target.value)} />
            <button className="btn btn-primary btn-sm" disabled={busy || !slot.trim()} onClick={() => act(() => apiC02.accept(id, slot.trim()), 'Accepted.')}>Accept</button>
            <select className="input w-auto" defaultValue="" onChange={e => { if (e.target.value && window.confirm('Decline this case? It will go to another mentor.')) act(() => apiC02.decline(id, e.target.value), 'Declined.', () => nav('/mentor-console')) ; e.target.value = '' }}>
              <option value="">Decline…</option><option value="busy">I'm too busy</option><option value="outside_expertise">Outside my expertise</option><option value="conflict">Conflict of interest</option><option value="other">Other reason</option></select>
          </div>
        </Callout>)}

      <div className="grid lg:grid-cols-[1fr_380px] gap-5">
        <div className="space-y-4 min-w-0">
          <div className="card p-4 flex flex-col" style={{ minHeight: 320 }}>
            <div className="eyebrow mb-2">Conversation <span className="normal-case font-semibold text-muted">· inside SAARTHI only · contact details are blocked</span></div>
            <div className="flex-1 space-y-2 overflow-auto max-h-[380px] pr-1" aria-live="polite">
              {c.messages.map((m: any) => (
                <div key={m.id} translate={m.sender === 'system' ? undefined : 'no'} className={`text-sm rounded-2xl px-3.5 py-2 max-w-[88%] ${m.sender === 'mentor' ? 'bg-navy text-white ml-auto' : m.sender === 'learner' ? 'bg-teal-soft' : 'bg-paper text-muted italic text-xs'}`}>
                  {m.sender === 'learner' && <div className="text-[11px] font-extrabold text-teal mb-0.5">{c.report?.learner?.first_name}</div>}{m.text}</div>))}
              <div ref={end} />
            </div>
            {working && (
              <div className="flex gap-2 mt-3"><input className="input" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && text.trim()) act(async () => { const r = await apiC02.message(id, text); if (r.blocked) { toast(r.reason, 'warn') } else setText(''); return null }) }} placeholder="Message the learner…" aria-label="Message" />
                <button className="btn btn-primary" disabled={busy || !text.trim()} onClick={() => act(async () => { const r = await apiC02.message(id, text); if (r.blocked) toast(r.reason, 'warn'); else setText(''); return null })}>Send</button></div>)}
          </div>

          {['accepted', 'scheduled'].includes(c.status) && <button className="btn btn-saffron" disabled={busy} onClick={() => act(() => apiC02.held(id), 'Marked as held.')}>The session was held</button>}

          {working && (
            <div className="card p-4 space-y-3">
              <SectionTitle eyebrow="After the session" title="Record the outcome" />
              <label className="block text-sm font-semibold">What did you cover?<textarea className="input mt-1 min-h-[80px]" value={notes} maxLength={1500} onChange={e => setNotes(e.target.value)} /></label>
              <label className="block text-sm font-semibold">Next step for the learner<input className="input mt-1" value={next} maxLength={300} onChange={e => setNext(e.target.value)} /></label>
              <div><div className="text-sm font-semibold">How well did the learner show they understand this in the session?</div>
                <div className="flex gap-1.5 flex-wrap mt-1" role="radiogroup">{SCALE.map((l, i) => <button key={l} role="radio" aria-checked={demo === i + 1} onClick={() => setDemo(i + 1)} className={`btn btn-sm ${demo === i + 1 ? 'btn-primary' : 'btn-ghost'}`}>{l}</button>)}</div>
                <p className="text-xs text-muted mt-1">This is about the learner's understanding, not how good the session was. It is recorded as one piece of evidence; the follow-up check judges whether it helped.</p></div>
              <button className="btn btn-primary" disabled={busy || notes.trim().length < 10} onClick={() => act(() => apiC02.outcome(id, notes, next, demo), 'Outcome recorded.')}>Save outcome</button>
            </div>)}
          {c.outcome && <Callout tone="navy" title="Outcome recorded">{c.outcome.notes}<div className="mt-1 font-semibold">Next: {c.outcome.next_step}</div></Callout>}
          {typeof c.followup?.p_now === 'number' && <Callout tone={c.followup.improved ? 'teal' : 'saffron'} title="Follow-up result">Learner's estimate: {Math.round(c.followup.p_at_open * 100)}% → <b>{Math.round(c.followup.p_now * 100)}%</b> ({c.followup.gain >= 0 ? '+' : ''}{Math.round(c.followup.gain * 100)} points).</Callout>}
        </div>

        <aside className="card p-4 space-y-3 h-fit">
          <div className="eyebrow">Case report</div>
          <CaseReport report={c.report} />
          <button className="btn btn-ghost btn-sm w-full" onClick={() => { const d = window.prompt('What worries you about this learner? A safeguarding lead will read it.'); if (d) act(async () => { const r = await apiC02.flag(id, d); toast(r.message); return null }) }}>I'm worried about this learner</button>
          <div className="text-[11px] text-muted">Only what is listed here is shared with you. You cannot change the learner's mastery: your outcome is recorded as evidence with its own weight.</div>
        </aside>
      </div>
    </div>
  )
}
