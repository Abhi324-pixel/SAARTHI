import { useEffect, useState } from 'react'
import { apiC01 } from '../api_ext/C01'
import { apiC02 } from '../api_ext/C02'
import { Callout, SectionTitle, Spinner } from '../components/ui'
import { useApp } from '../store'

const KINDS: [string, string][] = [['identity', 'Identity checked'], ['reference', 'Reference checked'], ['interview', 'Interviewed'], ['police_verification', 'Police verification']]

/** Safeguarding lead: review mentor applications and manage real mentors. Access is decided by the server (SAARTHI_ADMINS). */
export default function Admin() {
  const { me, toast } = useApp()
  const [apps, setApps] = useState<any[] | null>(null)
  const [mentors, setMentors] = useState<any | null>(null)
  const [sel, setSel] = useState<any | null>(null)
  const [note, setNote] = useState('')
  const [checks, setChecks] = useState<string[]>([])
  const [status, setStatus] = useState('submitted')
  const [denied, setDenied] = useState(false)
  const [reports, setReports] = useState<any[]>([])

  const load = () => {
    apiC01.adminApplications(status || undefined).then(r => setApps(r.applications)).catch((e: any) => { if (e.status === 403 || e.status === 404) setDenied(true); else toast(e.message, 'err') })
    apiC01.adminMentors().then(setMentors).catch(() => {})
    apiC02.adminReports('open').then(r => setReports(r.reports)).catch(() => {})
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [status])

  async function decide(decision: string) {
    try { await apiC01.adminDecide(sel.id, decision, note, decision === 'approve' ? checks.map(kind => ({ kind })) : []); toast('Recorded.'); setSel(null); setNote(''); setChecks([]); load() }
    catch (e: any) { toast(e.message, 'err') }
  }
  async function suspend(m: any) {
    const why = window.prompt(`Why suspend ${m.name}? (required, recorded in the audit log)`)
    if (!why) return
    try { const r = await apiC01.adminSuspend(m.id, why); toast(`Suspended. ${r.cases_rematched} case(s) re-matched.`); load() } catch (e: any) { toast(e.message, 'err') }
  }

  async function resolveReport(r: any) {
    const note = window.prompt('How was this resolved? (required, recorded in the audit log)')
    if (!note) return
    try { await apiC02.adminResolve(r.id, note); toast('Closed.'); load() } catch (e: any) { toast(e.message, 'err') }
  }

  if (denied) return <div className="max-w-xl mx-auto"><Callout tone="navy" title="Not available">This page is for the SAARTHI safeguarding team, and only when real mentors are switched on.</Callout></div>
  if (!apps) return <div className="py-16 flex justify-center"><Spinner /></div>

  return (
    <div className="space-y-5">
      <div><div className="eyebrow">Safeguarding lead · {me?.name}</div><h1 className="h-page">Mentor review</h1></div>
      <div className="grid lg:grid-cols-[360px_1fr] gap-5">
        <section className="card p-4 space-y-2">
          <SectionTitle eyebrow="Applications" title="Queue" right={<select className="input w-auto text-xs" value={status} onChange={e => { setStatus(e.target.value); setSel(null) }}><option value="submitted">Submitted</option><option value="needs_info">Needs info</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="">All</option></select>} />
          {apps.length === 0 && <div className="text-sm text-muted">Nothing here.</div>}
          {apps.map(a => <button key={a.id} onClick={() => { setSel(a); setNote(''); setChecks([]) }} className={`w-full text-left rounded-xl border px-3 py-2 ${sel?.id === a.id ? 'border-saffron bg-saffron-soft' : 'border-line hover:bg-paper'}`}><b className="text-navy">{a.name || '(no name)'}</b> <span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{a.status.replace('_', ' ')}</span><div className="text-xs text-muted">{a.tier_requested.replace('_', ' ')} · {a.headline}</div></button>)}
        </section>
        <section className="card p-5 space-y-3 min-w-0">
          {!sel ? <div className="text-sm text-muted">Pick an application.</div> : (
            <>
              <div className="flex items-center gap-2 flex-wrap"><h2 className="text-xl font-extrabold text-navy">{sel.name}</h2><span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{sel.tier_requested.replace('_', ' ')}</span><span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{sel.status.replace('_', ' ')}</span></div>
              <div className="text-sm text-muted">{sel.headline} · {sel.years_experience} yrs{sel.organisation ? ` · ${sel.organisation}` : ''} · {sel.email ?? 'no e-mail on the account'}</div>
              <p className="text-sm bg-paper rounded-lg p-3">{sel.bio}</p>
              <div className="text-sm"><b>Topics:</b> {sel.expertise.join(', ') || '—'} · <b>Languages:</b> {sel.languages.join(', ')} · <b>Slots:</b> {sel.availability.join(', ') || '—'}</div>
              <div className="text-sm"><b>Code of conduct:</b> {sel.pledge_current ? `accepted ${sel.pledge_accepted_at}` : 'not accepted (current version)'}</div>
              <div className="rounded-xl border border-line p-3 text-sm space-y-1.5">
                <div className="font-bold">Screen {sel.screen_result?.mcq ? `· ${sel.screen_result.mcq.correct}/${sel.screen_result.mcq.asked} multiple-choice correct (input, not a gate)` : ''}</div>
                {Object.entries(sel.screen_result?.open ?? {}).map(([k, v]) => <div key={k}><span className="text-xs font-bold text-muted">{k.replace(/_/g, ' ')}</span><div className="bg-paper rounded p-2 whitespace-pre-wrap">{String(v)}</div></div>)}
              </div>
              {['submitted', 'needs_info'].includes(sel.status) && (
                <div className="space-y-2">
                  <div className="text-sm font-bold">Checks a human has really done (recorded with an approval)</div>
                  <div className="flex gap-3 flex-wrap text-sm">{KINDS.map(([k, l]) => <label key={k} className="flex items-center gap-1.5"><input type="checkbox" checked={checks.includes(k)} onChange={() => setChecks(c => c.includes(k) ? c.filter(x => x !== k) : [...c, k])} />{l}</label>)}</div>
                  <textarea className="input min-h-[70px]" placeholder="Note (required for every decision; the applicant sees it for 'needs info' and 'not accepted')" value={note} onChange={e => setNote(e.target.value)} />
                  <div className="flex gap-2 flex-wrap"><button className="btn btn-primary" disabled={!note.trim()} onClick={() => decide('approve')}>Approve</button><button className="btn btn-ghost" disabled={!note.trim()} onClick={() => decide('needs_info')}>Ask for more information</button><button className="btn btn-ghost" style={{ color: '#c62828' }} disabled={!note.trim()} onClick={() => decide('reject')}>Do not accept</button></div>
                </div>)}
            </>)}
        </section>
      </div>
      <section className="card p-4">
        <SectionTitle eyebrow="Safeguarding" title={`Open reports (${reports.length})`} />
        {reports.length === 0 && <div className="text-sm text-muted">No open reports.</div>}
        <div className="space-y-1.5">{reports.map(r => <div key={r.id} className="border border-line rounded-xl px-3 py-2 text-sm"><div className="flex items-center gap-2 flex-wrap"><span className="chip" style={{ background: '#fdeaea', color: '#c62828' }}>{r.category.replace('_', ' ')}</span><span className="text-xs text-muted">{r.created_at.replace('T', ' ')} · case {r.case_id ?? '—'} · reporter {r.reporter_id}</span><button className="btn btn-ghost btn-sm ml-auto" onClick={() => resolveReport(r)}>Close with a note</button></div><p className="mt-1 whitespace-pre-wrap">{r.detail}</p></div>)}</div>
      </section>
      <section className="card p-4">
        <SectionTitle eyebrow="Real mentors" title="Who can take cases" />
        {mentors && <p className="text-xs text-muted mb-2">Learners under 18 are only matched with mentors who have all of: {mentors.minor_policy.required_checks.map((k: string) => k.replace('_', ' ')).join(', ')}.</p>}
        {mentors?.mentors.length === 0 && <div className="text-sm text-muted">No approved mentors yet.</div>}
        <div className="space-y-1.5">{mentors?.mentors.map((m: any) => <div key={m.id} className="flex items-center gap-2 flex-wrap text-sm border border-line rounded-xl px-3 py-2"><b className="text-navy">{m.name}</b><span className="chip" style={{ background: '#eceff3', color: '#5b6675' }}>{m.tier.replace('_', ' ')}</span><span className="chip" style={{ background: m.status === 'verified' ? '#e2f4ea' : '#fdeaea', color: m.status === 'verified' ? '#1f6f45' : '#c62828' }}>{m.status}</span><span className="text-xs text-muted">checks: {m.checks.join(', ') || 'none'}{m.can_take_minors ? ' · can take under-18' : ''}</span>{m.status === 'verified' && <button className="btn btn-ghost btn-sm ml-auto" onClick={() => suspend(m)}>Suspend</button>}</div>)}</div>
      </section>
    </div>
  )
}
