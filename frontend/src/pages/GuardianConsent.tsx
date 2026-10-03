import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiD01 } from '../api_ext/D01'

// Public page opened from the e-mail a guardian receives. No account, no navigation, almost no data (spec D01).
const T = {
  english: {
    title: (n: string) => `${n} would like to talk to a SAARTHI mentor`,
    intro: 'SAARTHI is a learning app. Because they are under 18, a parent or guardian has to approve mentor sessions first.',
    what: 'If you approve, they can',
    see: 'What a mentor can see',
    safe: 'Mentor chats stay inside the app, sharing phone numbers or e-mail is blocked, and every message is logged. You can withdraw your approval any time.',
    approve: 'I approve', decline: 'I do not approve', working: 'Please wait…',
    doneApprove: 'Thank you. Approval recorded.', doneDecline: 'Thank you. We have recorded that you do not approve; nothing will happen.',
    withdrawHint: 'To withdraw your approval later, keep this link:', bad: 'This link is not valid any more. If you still want to help, ask the learner to send a new request.',
    wTitle: 'Withdraw your approval', wText: 'This stops mentor sessions for this learner and pauses any open cases.', wBtn: 'Withdraw approval', wDone: 'Your approval has been withdrawn.',
  },
  hindi: {
    title: (n: string) => `${n} SAARTHI मेंटर से बात करना चाहते हैं`,
    intro: 'SAARTHI एक सीखने वाला ऐप है। 18 वर्ष से कम होने के कारण पहले माता-पिता या अभिभावक की अनुमति ज़रूरी है।',
    what: 'आपकी अनुमति से वे कर सकेंगे',
    see: 'मेंटर क्या देख सकता है',
    safe: 'मेंटर की चैट ऐप के अंदर ही रहती है, फ़ोन नंबर या ईमेल साझा करना रोका जाता है और हर संदेश दर्ज होता है। आप कभी भी अनुमति वापस ले सकते हैं।',
    approve: 'मैं अनुमति देता/देती हूँ', decline: 'मैं अनुमति नहीं देता/देती', working: 'कृपया प्रतीक्षा करें…',
    doneApprove: 'धन्यवाद। अनुमति दर्ज हो गई।', doneDecline: 'धन्यवाद। आपका "अनुमति नहीं" दर्ज हो गया; कुछ नहीं होगा।',
    withdrawHint: 'बाद में अनुमति वापस लेने के लिए यह लिंक संभालकर रखें:', bad: 'यह लिंक अब मान्य नहीं है। मदद करना चाहें तो सीखने वाले से नया अनुरोध भेजने को कहें।',
    wTitle: 'अनुमति वापस लें', wText: 'इससे इस सीखने वाले के लिए मेंटर सत्र रुक जाएँगे और खुले केस रोक दिए जाएँगे।', wBtn: 'अनुमति वापस लें', wDone: 'आपकी अनुमति वापस ले ली गई है।',
  },
}

export default function GuardianConsent({ withdraw = false }: { withdraw?: boolean }) {
  const { token = '' } = useParams()
  const [pv, setPv] = useState<any | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'bad' | 'approved' | 'declined' | 'withdrawn'>('loading')
  const [wt, setWt] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [lang, setLang] = useState<'english' | 'hindi'>('english')
  const t = T[lang]

  useEffect(() => {
    if (withdraw) { setState('ready'); return }
    apiD01.guardianPreview(token).then(p => { setPv(p); setLang(p.lang === 'hindi' ? 'hindi' : 'english'); setState('ready') }).catch(() => setState('bad'))
  }, [token, withdraw])

  async function decide(d: 'approve' | 'decline') {
    setBusy(true)
    try { const r = await apiD01.guardianDecision(token, d); setWt(r.withdraw_token ?? null); setState(d === 'approve' ? 'approved' : 'declined') }
    catch { setState('bad') } finally { setBusy(false) }
  }
  async function doWithdraw() {
    setBusy(true)
    try { await apiD01.guardianWithdraw(token); setState('withdrawn') } catch { setState('bad') } finally { setBusy(false) }
  }

  return (
    <div className="min-h-full flex items-center justify-center p-4">
      <div className="card p-6 sm:p-8 w-full max-w-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="font-extrabold text-navy text-lg">SAARTHI</div>
          <button translate="no" className="text-xs underline" onClick={() => setLang(l => (l === 'english' ? 'hindi' : 'english'))}>{lang === 'english' ? 'हिन्दी' : 'English'}</button>
        </div>
        {state === 'loading' && <p className="text-muted">…</p>}
        {state === 'bad' && <p className="font-semibold">{t.bad}</p>}
        {state === 'ready' && withdraw && (
          <>
            <h1 className="h-page">{t.wTitle}</h1><p>{t.wText}</p>
            <button className="btn btn-primary" disabled={busy} onClick={doWithdraw}>{busy ? t.working : t.wBtn}</button>
          </>
        )}
        {state === 'ready' && !withdraw && pv && (
          <>
            <h1 className="h-page">{t.title(pv.learner_first_name)}</h1>
            <p>{t.intro}</p>
            <div><b>{t.what}:</b> {pv.scope_text}</div>
            <div><b>{t.see}:</b><ul className="list-disc pl-5 mt-1 space-y-0.5 text-sm">{pv.mentors_see.map((x: string) => <li key={x}>{x}</li>)}</ul></div>
            <p className="text-sm text-muted">{t.safe}</p>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-primary" disabled={busy} onClick={() => decide('approve')}>{busy ? t.working : t.approve}</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => decide('decline')}>{t.decline}</button>
            </div>
          </>
        )}
        {state === 'approved' && (
          <>
            <p className="font-semibold">{t.doneApprove}</p>
            {wt && <p className="text-sm">{t.withdrawHint}<br /><a className="underline break-all" href={`/guardian/withdraw/${wt}`}>{window.location.origin}/guardian/withdraw/{wt}</a></p>}
          </>
        )}
        {state === 'declined' && <p className="font-semibold">{t.doneDecline}</p>}
        {state === 'withdrawn' && <p className="font-semibold">{t.wDone}</p>}
      </div>
    </div>
  )
}
