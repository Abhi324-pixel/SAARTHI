import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiC01 } from '../api_ext/C01'
import { Callout, SectionTitle, Spinner } from '../components/ui'
import { useApp } from '../store'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const STATUS_TEXT: Record<string, string> = {
  draft: 'Draft — not submitted yet', submitted: 'Submitted — a reviewer will read it', needs_info: 'The reviewer needs more information',
  approved: 'Approved — you are a verified mentor', rejected: 'Not accepted',
}

/** Become a mentor: profile → short screen → code of conduct → submit. A person reviews it; nothing is verified automatically. */
export default function MentorApply() {
  const { toast } = useApp()
  const [data, setData] = useState<any | null>(null)
  const [off, setOff] = useState(false)
  const [form, setForm] = useState<any>({ tier_requested: 'skill_mentor', name: '', headline: '', bio: '', years_experience: 0, organisation: '', expertise: [], languages: ['english'], availability: [] })
  const [slot, setSlot] = useState({ day: 'Mon', time: '18:00' })
  const [screen, setScreen] = useState<any | null>(null)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [open, setOpen] = useState<Record<string, string>>({})
  const [plang, setPlang] = useState<'en' | 'hi'>('en')
  const [agree, setAgree] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = () => apiC01.myApplication().then(d => {
    setData(d)
    const a = d.application
    if (a) setForm({ tier_requested: a.tier_requested, name: a.name, headline: a.headline, bio: a.bio, years_experience: a.years_experience, organisation: a.organisation, expertise: a.expertise, languages: a.languages, availability: a.availability })
  }).catch((e: any) => { if (e.status === 404) setOff(true); else toast(e.message, 'err') })
  useEffect(() => { load() /* eslint-disable-next-line */ }, [])

  async function run(fn: () => Promise<any>, ok?: string) {
    setBusy(true)
    try { await fn(); if (ok) toast(ok); await load() } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  const toggle = (key: 'expertise' | 'languages', v: string) => setForm((f: any) => ({ ...f, [key]: f[key].includes(v) ? f[key].filter((x: string) => x !== v) : [...f[key], v] }))

  if (off) return <div className="max-w-2xl mx-auto"><Callout tone="navy" title="Not available in demo mode">Mentor sign-up is only switched on with real mentors. <Link className="underline font-bold" to="/mentors">Back to SAKHA</Link></Callout></div>
  if (!data) return <div className="py-16 flex justify-center"><Spinner /></div>
  const a = data.application
  const locked = a && !['draft', 'needs_info'].includes(a.status)

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div><div className="eyebrow">SAKHA</div><h1 className="h-page">Become a mentor</h1>
        <p className="text-muted mt-1">Tell us about yourself, answer a short screen, and accept the code of conduct. A person on the SAARTHI safeguarding team reviews every application and decides — nothing is verified automatically.</p></div>

      {a && <Callout tone={a.status === 'approved' ? 'teal' : a.status === 'rejected' ? 'red' : 'saffron'} title={STATUS_TEXT[a.status]}>{a.reviewer_note || (a.status === 'submitted' ? 'You will see the decision here.' : '')}</Callout>}

      <section className="card p-5 space-y-3">
        <SectionTitle eyebrow="1 · Profile" title="About you" />
        <fieldset disabled={locked || busy} className="space-y-3">
          <div className="flex gap-2" role="radiogroup" aria-label="Type of mentor">
            {[['skill_mentor', 'Skill Mentor', 'Technical help for learners'], ['margdarshak', 'Margdarshak', 'Career and guidance']].map(([v, l, d]) => (
              <button type="button" key={v} role="radio" aria-checked={form.tier_requested === v} onClick={() => setForm({ ...form, tier_requested: v })}
                className={`flex-1 text-left rounded-xl border p-3 ${form.tier_requested === v ? 'border-saffron bg-saffron-soft ring-2 ring-saffron/30' : 'border-line'}`}><b className="text-navy block">{l}</b><span className="text-xs text-muted">{d}</span></button>))}
          </div>
          <label className="block text-sm font-semibold">Your name (shown to learners)<input className="input mt-1" value={form.name} maxLength={120} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
          <label className="block text-sm font-semibold">One-line headline<input className="input mt-1" value={form.headline} maxLength={120} placeholder="e.g. Backend engineer, 6 years in fintech" onChange={e => setForm({ ...form, headline: e.target.value })} /></label>
          <label className="block text-sm font-semibold">Short bio <span className="text-muted font-normal">({form.bio.length}/600)</span><textarea className="input mt-1 min-h-[90px]" value={form.bio} maxLength={600} onChange={e => setForm({ ...form, bio: e.target.value })} /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm font-semibold">Years of experience<input className="input mt-1" type="number" min={0} max={60} value={form.years_experience} onChange={e => setForm({ ...form, years_experience: parseInt(e.target.value || '0') })} /></label>
            <label className="block text-sm font-semibold">Organisation (optional)<input className="input mt-1" value={form.organisation} maxLength={160} onChange={e => setForm({ ...form, organisation: e.target.value })} /></label>
          </div>
          <div><div className="text-sm font-semibold mb-1">Languages</div><div className="flex gap-3 flex-wrap text-sm">{data.options.languages.map((l: string) => <label key={l} className="flex items-center gap-1.5"><input type="checkbox" checked={form.languages.includes(l)} onChange={() => toggle('languages', l)} />{l}</label>)}</div></div>
          <div><div className="text-sm font-semibold mb-1">Topics you can help with (up to 10)</div>
            <div className="flex flex-wrap gap-1.5">{data.options.expertise.map((t: string) => <button type="button" key={t} aria-pressed={form.expertise.includes(t)} onClick={() => toggle('expertise', t)} className={`chip ${form.expertise.includes(t) ? 'ring-2 ring-saffron' : ''}`} style={{ background: form.expertise.includes(t) ? '#fdf3e9' : '#eceff3', color: '#16324f' }}>{t.replace(/_/g, ' ')}</button>)}</div></div>
          <div><div className="text-sm font-semibold mb-1">Weekly availability <span className="text-muted font-normal">(India time)</span></div>
            <div className="flex flex-wrap gap-1.5 mb-2">{form.availability.map((s: string) => <button type="button" key={s} className="chip" style={{ background: '#e3f2f1', color: '#0f5d5d' }} onClick={() => setForm({ ...form, availability: form.availability.filter((x: string) => x !== s) })}>{s} ✕</button>)}</div>
            <div className="flex gap-2 items-center"><select className="input w-24" value={slot.day} onChange={e => setSlot({ ...slot, day: e.target.value })}>{DAYS.map(d => <option key={d}>{d}</option>)}</select>
              <input className="input w-28" type="time" value={slot.time} onChange={e => setSlot({ ...slot, time: e.target.value })} />
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => { const s = `${slot.day} ${slot.time}`; if (!form.availability.includes(s) && form.availability.length < 14) setForm({ ...form, availability: [...form.availability, s] }) }}>Add slot</button></div></div>
          <button type="button" className="btn btn-primary" onClick={() => run(() => apiC01.saveProfile(form), 'Saved.')}>{busy ? 'Saving…' : 'Save profile'}</button>
        </fieldset>
      </section>

      {a && (
        <section className="card p-5 space-y-3">
          <SectionTitle eyebrow="2 · Short screen" title={a.screen_done ? 'Done ✓' : 'A few questions'} />
          <p className="text-sm text-muted">This is read by the reviewer together with your profile. It is not a pass/fail test.</p>
          {!locked && !screen && <button className="btn btn-ghost" onClick={() => apiC01.screenQuestions().then(setScreen).catch((e: any) => toast(e.message, 'err'))}>{a.screen_done ? 'Redo the screen' : 'Start the screen'}</button>}
          {screen && !locked && (
            <div className="space-y-4">
              {screen.mcq.map((q: any, n: number) => (
                <div key={q.id}><div className="font-semibold text-sm">{n + 1}. {q.stem}</div>
                  <div className="mt-1 space-y-1">{q.options.map((o: any) => <label key={o.index} className="flex items-start gap-2 text-sm"><input type="radio" name={q.id} checked={answers[q.id] === o.index} onChange={() => setAnswers({ ...answers, [q.id]: o.index })} /><span>{o.text}</span></label>)}</div></div>))}
              {screen.open.map((o: any) => <label key={o.key} className="block text-sm font-semibold">{o.prompt}<textarea className="input mt-1 min-h-[80px]" value={open[o.key] ?? ''} maxLength={1500} onChange={e => setOpen({ ...open, [o.key]: e.target.value })} /></label>)}
              <button className="btn btn-primary" disabled={busy} onClick={() => run(async () => { await apiC01.submitScreen(answers, open); setScreen(null) }, 'Screen saved.')}>Save my answers</button>
            </div>)}
        </section>
      )}

      {a && (
        <section className="card p-5 space-y-3">
          <SectionTitle eyebrow="3 · Code of conduct" title="My promises as a mentor" right={<button className="text-xs underline" onClick={() => setPlang(plang === 'en' ? 'hi' : 'en')}>{plang === 'en' ? 'हिन्दी' : 'English'}</button>} />
          <ul className="list-disc pl-5 space-y-1.5 text-sm">{data.pledge.promises.map((p: any) => <li key={p.id}>{p[plang]}</li>)}</ul>
          {a.pledge_current ? <p className="text-sm font-semibold text-lvl-proficient">✓ You accepted the current version.</p> : !locked && (
            <div className="space-y-2"><label className="flex items-start gap-2 text-sm font-semibold"><input type="checkbox" className="mt-1" checked={agree} onChange={e => setAgree(e.target.checked)} />I have read these promises and I agree to keep them.</label>
              <button className="btn btn-ghost" disabled={!agree || busy} onClick={() => run(() => apiC01.acceptPledge(data.pledge.version), 'Recorded.')}>Accept the code of conduct</button></div>)}
        </section>
      )}

      {a && !locked && <div className="card p-5"><button className="btn btn-saffron py-3 px-8" disabled={busy} onClick={() => run(() => apiC01.submitApplication(), 'Submitted for review.')}>Submit my application</button>
        <p className="text-xs text-muted mt-2">Submitting is only possible when your profile, the screen and the code of conduct are complete; if something is missing we will say what.</p></div>}
    </div>
  )
}
