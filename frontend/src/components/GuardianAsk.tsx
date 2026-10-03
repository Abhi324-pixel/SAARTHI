import { useState } from 'react'
import { apiD01 } from '../api_ext/D01'
import { useApp } from '../store'

/** Real consent (SAARTHI_CONSENT=db): a minor gives a parent/guardian e-mail; the guardian gets a link. The link never reaches this browser. */
export default function GuardianAsk({ consent, onChange }: { consent: any; onChange: () => void }) {
  const { toast, me } = useApp()
  const [email, setEmail] = useState('')
  const [lang, setLang] = useState<'english' | 'hindi'>(me?.language === 'hindi' ? 'hindi' : 'english')
  const [busy, setBusy] = useState(false)
  const [outbox, setOutbox] = useState<any[] | null>(null)
  const r = consent.request as { status: string; masked_email: string | null; sent_at: string } | null | undefined
  const waiting = r?.status === 'sent'

  async function send(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try { await apiD01.requestGuardian(email.trim(), lang); toast('E-mail sent to your parent or guardian.'); setEmail(''); onChange() }
    catch (err: any) { toast(err.message, 'err') } finally { setBusy(false) }
  }

  return (
    <div className="mt-3 space-y-2 text-sm">
      {waiting && <div className="rounded-xl bg-white/10 text-white border border-white/10 p-3 leading-relaxed"><b>Waiting for your guardian</b> — we e-mailed {r?.masked_email}. They only need to open the link and tap Approve. You can send it again to a different address below.</div>}
      {r?.status === 'declined' && <div className="rounded-xl bg-red-500/15 text-red-200 border border-red-500/30 p-3 leading-relaxed">Your guardian chose not to approve mentor sessions. You can still use every learning feature.</div>}
      {r?.status === 'withdrawn' && <div className="rounded-xl bg-amber-500/15 text-amber-200 border border-amber-500/30 p-3 leading-relaxed">Your guardian withdrew their approval. Open cases are paused.</div>}
      <form onSubmit={send} className="flex flex-wrap items-end gap-2">
        <label className="font-semibold">Parent or guardian's e-mail
          <input className="input mt-1 w-64" type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="parent@example.com" autoComplete="off" />
        </label>
        <label className="font-semibold">E-mail language
          <select translate="no" className="input mt-1" value={lang} onChange={e => setLang(e.target.value as any)}><option value="english">English</option><option value="hindi">हिन्दी</option></select>
        </label>
        <button className="btn btn-primary btn-sm" disabled={busy || !email.trim()}>{busy ? 'Sending…' : waiting ? 'Send again' : 'Ask my guardian'}</button>
      </form>
      <p className="text-xs text-muted">We send one short e-mail with a private link. Your guardian sees only your first name and what a mentor can see; they need no account.</p>
      {consent.dev_outbox && (
        <div className="text-xs">
          <button className="underline font-semibold" onClick={async () => { try { setOutbox((await apiD01.devOutbox()).messages) } catch { setOutbox([]) } }}>Dev only: show the e-mail that would be sent</button>
          {outbox && <pre className="mt-1 bg-paper rounded p-2 whitespace-pre-wrap break-words">{outbox.length ? outbox[outbox.length - 1].text : 'No message yet.'}</pre>}
        </div>
      )}
    </div>
  )
}
