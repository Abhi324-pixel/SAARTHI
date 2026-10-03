import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, tokenStore } from '../api'
import { DemoBadge } from '../components/ui'
import { supabase, supabaseConfigured } from '../supabase'
import { useApp } from '../store'

export default function Login() {
  const { refreshMe, toast, health } = useApp()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [age, setAge] = useState(20)
  const [language, setLanguage] = useState('hinglish')
  const [busy, setBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signup' | 'signin'>('signup')
  const [notice, setNotice] = useState<string | null>(null)
  const real = health?.adapters?.auth === 'supabase'
  const [demo, setDemo] = useState<{ id: string; name: string; role: string; note: string }[]>([])
  const [demoOpen, setDemoOpen] = useState(false)
  // dev-only: the backend answers 404 outside a local mock-auth setup, so the menu never shows for real sign-in
  useEffect(() => { if (health?.adapters?.auth === 'mock') api.demoAccounts().then(r => setDemo(r.accounts)).catch(() => setDemo([])) }, [health?.adapters?.auth])

  async function demoGo(id: string, role: string) {
    setBusy(true)
    try {
      const r = await api.demoLogin(id)
      tokenStore.set(r.token)
      await refreshMe()
      nav(role === 'mentor' ? '/mentor-console' : '/')
    } catch (err: any) { toast(err.message, 'err') } finally { setBusy(false); setDemoOpen(false) }
  }

  async function google() {
    if (!supabase) { toast('Supabase is not configured in the browser: set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env.local and restart the dev server.', 'err'); return }
    setBusy(true)
    const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })
    if (error) { toast(error.message, 'err'); setBusy(false) }   // on success the browser leaves for Google; the session is picked up when it returns
  }

  async function go(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      if (real) {
        if (!supabase) throw new Error('Supabase is not configured in the browser: set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env.local and restart the dev server.')
        setNotice(null)
        if (mode === 'signup') {
          const { data, error } = await supabase.auth.signUp({ email, password, options: { data: { name, age, language } } })
          if (error) throw error
          if (!data.session) { setNotice('Account created. Check your email and click the confirmation link, then sign in here.'); setMode('signin'); return }
          tokenStore.set(data.session.access_token)
        } else {
          const { data, error } = await supabase.auth.signInWithPassword({ email, password })
          if (error) throw error
          tokenStore.set(data.session.access_token)
        }
        await refreshMe()
        nav(mode === 'signup' ? '/onboarding' : '/')
        return
      }
      const r = await api.login({ name, age, language })
      tokenStore.set(r.token)
      await refreshMe()
      nav('/onboarding')
    } catch (err: any) { toast(err.message, 'err') } finally { setBusy(false) }
  }

  return (
    <div className="min-h-full grid lg:grid-cols-2 relative">
      {demo.length > 0 && (
        <div className="absolute top-3 right-3 z-20 text-sm">
          <button type="button" className="btn btn-sm btn-ghost bg-white/90" aria-expanded={demoOpen} onClick={() => setDemoOpen(o => !o)}>☰ Demo accounts</button>
          {demoOpen && (
            <div className="mt-1 w-64 bg-white rounded-xl shadow-2xl border border-line overflow-hidden" role="menu">
              <div className="px-3 py-2 text-[11px] text-muted border-b border-line">Fake accounts for this machine only</div>
              {demo.map(a => (
                <button key={a.id} type="button" role="menuitem" disabled={busy} className="w-full text-left px-3 py-2 hover:bg-paper border-b border-line last:border-0" onClick={() => demoGo(a.id, a.role)}>
                  <div className="font-semibold text-navy">{a.name}</div><div className="text-[11px] text-muted">{a.role === 'mentor' ? 'Mentor' : 'Learner'} · {a.note}</div>
                </button>))}
            </div>)}
        </div>)}
      <section className="bg-navy text-white p-8 lg:p-14 flex flex-col justify-center relative overflow-hidden">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-saffron/20 blur-3xl" aria-hidden />
        <div className="relative max-w-lg">
          <div className="inline-flex items-center gap-2 mb-6">
            <span className="inline-flex h-10 w-10 rounded-xl bg-white/10 items-center justify-center"><svg width="26" height="26" viewBox="0 0 64 64"><path d="M18 44c8 6 24 4 24-6 0-12-22-6-22-16 0-8 14-10 22-4" fill="none" stroke="#E07A1F" strokeWidth="7" strokeLinecap="round" /></svg></span>
            <span className="text-2xl font-extrabold tracking-tight">SAARTHI</span>
          </div>
          <h1 className="text-4xl lg:text-5xl font-extrabold leading-tight tracking-tight">An AI mentor that learns <span className="text-saffron">how to teach you.</span></h1>
          <p className="mt-4 text-white/80 text-lg leading-relaxed">Not another quiz app. SAARTHI listens to you explain, checks the SQL you write, finds the <i>exact</i> idea you've got wrong — and rebuilds your roadmap around it. When it can't help, a human mentor gets the full story.</p>
          <ul className="mt-6 space-y-2.5 text-white/90">
            <li className="flex gap-3"><span className="text-saffron font-bold">①</span> Talk in Hindi, English or Hinglish — voice by ElevenLabs</li>
            <li className="flex gap-3"><span className="text-saffron font-bold">②</span> “Teach it back to me” — scored from your own words, quote by quote</li>
            <li className="flex gap-3"><span className="text-saffron font-bold">③</span> Every roadmap change comes with a reason you can read</li>
            <li className="flex gap-3"><span className="text-saffron font-bold">④</span> Chhatrachhaya mentors step in with a complete case report</li>
          </ul>
        </div>
      </section>
      <section className="p-6 lg:p-14 flex items-center justify-center">
        <form onSubmit={go} className="card p-7 w-full max-w-md space-y-4">
          <div><div className="eyebrow">Get started</div><h2 className="text-2xl font-extrabold text-navy">Create your learner profile</h2></div>
          {real && (
            <div className="flex gap-2" role="tablist">
              <button type="button" role="tab" aria-selected={mode === 'signup'} className={`btn btn-sm ${mode === 'signup' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setMode('signup')}>Create account</button>
              <button type="button" role="tab" aria-selected={mode === 'signin'} className={`btn btn-sm ${mode === 'signin' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setMode('signin')}>Sign in</button>
            </div>
          )}
          {real && !supabaseConfigured && <p className="text-xs bg-[#fdeaea] text-lvl-unknown rounded-lg p-2.5 font-semibold">Supabase keys are missing in the browser build: add VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY to frontend/.env.local.</p>}
          {notice && <p className="text-sm bg-teal-soft rounded-lg p-2.5 font-semibold" role="status">{notice}</p>}
          {real && (
            <>
              <label className="block text-sm font-semibold">Email<input className="input mt-1" type="email" required value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" /></label>
              <label className="block text-sm font-semibold">Password<input className="input mt-1" type="password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} /></label>
            </>
          )}
          {(!real || mode === 'signup') && <>
          <label className="block text-sm font-semibold">Your name
            <input className="input mt-1" required value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Priya Sharma" autoFocus={!real} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm font-semibold">Age
              <input className="input mt-1" type="number" min={10} max={100} required value={age} onChange={e => setAge(parseInt(e.target.value || '0'))} />
            </label>
            <label className="block text-sm font-semibold">Language
              <select translate="no" className="input mt-1" value={language} onChange={e => setLanguage(e.target.value)}>
                <option value="english">English</option><option value="hindi">हिन्दी (Hindi)</option><option value="hinglish">Hinglish</option>
              </select>
            </label>
          </div>
          {age > 0 && age < 18 && <p className="text-xs bg-saffron-soft rounded-lg p-2.5 text-ink/80">Under 18? You can use every learning feature. Mentor sessions need a parent or guardian's approval first.</p>}
          </>}
          <button className="btn btn-saffron w-full py-3 text-base" disabled={busy || (real && mode === 'signin' ? !email || !password : !name.trim() || age < 10 || (real && (!email || password.length < 8)))}>{busy ? 'Please wait…' : real && mode === 'signin' ? 'Sign in →' : real ? 'Create account →' : 'Continue →'}</button>
          {real && (
            <>
              <div className="flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" /></div>
              <button type="button" className="btn btn-ghost w-full py-2.5" disabled={busy} onClick={google}>
                <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z"/><path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 010-9.4l-7.9-6.1a24 24 0 000 21.6l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.9 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z"/></svg>
                Continue with Google
              </button>
              <p className="text-[11px] text-muted">With Google we will ask for your age once, because learners under 18 get extra protection.</p>
            </>
          )}
          {!real && <p className="text-[11px] text-muted flex items-center gap-1.5 flex-wrap">Demo sign-in (no password). <DemoBadge label="mock auth" title="Real sign-in is switched on with SAARTHI_AUTH=supabase." /></p>}
          {health && !health.ok && <p className="text-xs text-lvl-unknown font-semibold">Can't reach the SAARTHI API. Start the backend (see README) and refresh.</p>}
        </form>
      </section>
    </div>
  )
}
