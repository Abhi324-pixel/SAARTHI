import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiC07 } from '../api_ext/C07'
import { useApp } from '../store'

/** Shown once after a Google sign-up: Google does not give us an age, and SAARTHI's safety rules for under-18s depend on it. */
export default function CompleteProfile() {
  const { me, refreshMe, toast, logout } = useApp()
  const nav = useNavigate()
  const [name, setName] = useState(me?.name ?? '')
  const [age, setAge] = useState<number | ''>('')
  const [language, setLanguage] = useState(me?.language ?? 'hinglish')
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (age === '') return
    setBusy(true)
    try {
      await apiC07.completeProfile({ age, name: name.trim() || undefined, language })
      await refreshMe()
      nav('/onboarding', { replace: true })
    } catch (err: any) { toast(err.message, 'err') } finally { setBusy(false) }
  }

  return (
    <div className="min-h-full flex items-center justify-center p-4">
      <form onSubmit={submit} className="card p-6 sm:p-8 w-full max-w-md space-y-4">
        <div><div className="eyebrow">One more step</div><h1 className="h-page">Tell us a little about you</h1>
          <p className="text-muted mt-1 text-sm">Google doesn't share your age. SAARTHI asks because learners under 18 get extra protection — for example, a parent or guardian approves before you can talk to a mentor.</p></div>
        <label className="block text-sm font-semibold">Your name
          <input className="input mt-1" required value={name} onChange={e => setName(e.target.value)} maxLength={80} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm font-semibold">Age
            <input className="input mt-1" type="number" min={10} max={100} required value={age} onChange={e => setAge(e.target.value === '' ? '' : parseInt(e.target.value))} />
          </label>
          <label className="block text-sm font-semibold">Language
            <select translate="no" className="input mt-1" value={language} onChange={e => setLanguage(e.target.value)}>
              <option value="english">English</option><option value="hindi">हिन्दी (Hindi)</option><option value="hinglish">Hinglish</option>
            </select>
          </label>
        </div>
        {typeof age === 'number' && age > 0 && age < 18 && <p className="text-xs bg-saffron-soft rounded-lg p-2.5 text-ink/80">Under 18? You can use every learning feature. Mentor sessions need a parent or guardian's approval first.</p>}
        <p className="text-xs text-muted">Please enter your real age. It can't be changed later in the app.</p>
        <div className="flex items-center gap-3">
          <button className="btn btn-saffron py-2.5 px-6" disabled={busy || age === '' || age < 10 || age > 100}>{busy ? 'Saving…' : 'Continue →'}</button>
          <button type="button" className="text-xs underline text-muted" onClick={logout}>Sign out</button>
        </div>
      </form>
    </div>
  )
}
