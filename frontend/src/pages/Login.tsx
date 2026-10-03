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
  useEffect(() => {
    if (health?.adapters?.auth === 'mock') {
      api.demoAccounts().then(r => setDemo(r.accounts)).catch(() => setDemo([]))
    }
  }, [health?.adapters?.auth])

  async function demoGo(id: string, role: string) {
    setBusy(true)
    try {
      const r = await api.demoLogin(id)
      tokenStore.set(r.token)
      await refreshMe()
      nav(role === 'mentor' ? '/mentor-console' : '/')
    } catch (err: any) {
      toast(err.message, 'err')
    } finally {
      setBusy(false)
      setDemoOpen(false)
    }
  }

  async function google() {
    if (!supabase) {
      toast('Supabase is not configured in the browser: set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env.local and restart the dev server.', 'err')
      return
    }
    setBusy(true)
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin }
    })
    if (error) {
      toast(error.message, 'err')
      setBusy(false)
    }
  }

  async function go(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      if (real) {
        if (!supabase) {
          throw new Error('Supabase is not configured in the browser: set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env.local and restart the dev server.')
        }
        setNotice(null)
        if (mode === 'signup') {
          const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: { data: { name, age, language } }
          })
          if (error) throw error
          if (!data.session) {
            setNotice('Account created. Check your email and click the confirmation link, then sign in here.')
            setMode('signin')
            return
          }
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
    } catch (err: any) {
      toast(err.message, 'err')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-full grid lg:grid-cols-2 relative">
      {demo.length > 0 && (
        <div className="absolute top-4 right-4 z-20 text-sm">
          <button
            type="button"
            className="btn btn-sm btn-secondary backdrop-blur-md border border-[rgba(210,225,235,0.2)] flex items-center gap-1.5"
            aria-expanded={demoOpen}
            onClick={() => setDemoOpen(o => !o)}
          >
            ☰ Demo accounts
          </button>
          {demoOpen && (
            <div className="mt-1.5 w-68 card p-1.5 shadow-2xl backdrop-blur-2xl border border-[rgba(210,225,235,0.2)] overflow-hidden" role="menu">
              <div className="px-3 py-1.5 text-[11px] text-slate-400 border-b border-[rgba(210,225,235,0.12)] font-mono">
                Fake accounts for this machine only
              </div>
              <div className="max-h-64 overflow-y-auto divide-y divide-[rgba(210,225,235,0.08)]">
                {demo.map(a => (
                  <button
                    key={a.id}
                    type="button"
                    role="menuitem"
                    disabled={busy}
                    className="w-full text-left px-3 py-2 hover:bg-[rgba(255,255,255,0.06)] rounded-lg transition-colors"
                    onClick={() => demoGo(a.id, a.role)}
                  >
                    <div className="font-semibold text-white text-xs">{a.name}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{a.role === 'mentor' ? 'Mentor' : 'Learner'} · {a.note}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <section 
        className="text-white p-8 lg:p-14 flex flex-col justify-center relative overflow-hidden bg-cover bg-center"
        style={{
          backgroundImage: `radial-gradient(ellipse at 50% 50%, rgba(7, 19, 29, 0.65) 0%, rgba(5, 14, 22, 0.88) 100%), url('/background.jpg')`
        }}
      >
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[#FF8A24]/15 blur-3xl pointer-events-none" aria-hidden />
        <div className="relative max-w-lg">
          <div className="inline-flex items-center gap-3.5 mb-6">
            <span className="relative inline-flex h-14 w-14 rounded-2xl overflow-hidden bg-black/40 backdrop-blur-md items-center justify-center border border-[rgba(255,138,36,0.45)] shadow-[0_0_20px_rgba(255,138,36,0.3)]">
              <img src="/logo.png" alt="SAARTHI Logo" className="w-full h-full object-cover" />
            </span>
            <div className="flex flex-col">
              <span className="text-2xl font-extrabold tracking-tight text-white heading-glow leading-none">SAARTHI</span>
              <span className="text-[10px] uppercase tracking-widest text-[var(--accent-orange)] font-bold mt-1">Your guide to a brighter tomorrow</span>
            </div>
          </div>
          <h1 className="text-3xl lg:text-5xl font-extrabold leading-tight tracking-tight text-white heading-glow">
            An AI mentor that learns <span className="text-[#FF8A24]">how to teach you.</span>
          </h1>
          <p className="mt-4 text-slate-300 text-base lg:text-lg leading-relaxed desc-glow">
            Not another quiz app. SAARTHI listens to you explain, checks the SQL you write, finds the <i>exact</i> idea you've got wrong — and rebuilds your roadmap around it. When it can't help, a human mentor gets the full story.
          </p>
          <ul className="mt-6 space-y-3 text-slate-200 desc-glow">
            <li className="flex gap-3 items-center"><span className="text-[#FF8A24] font-bold">①</span> Talk in Hindi, English or Hinglish — voice by ElevenLabs</li>
            <li className="flex gap-3 items-center"><span className="text-[#FF8A24] font-bold">②</span> “Teach it back to me” — scored from your own words, quote by quote</li>
            <li className="flex gap-3 items-center"><span className="text-[#FF8A24] font-bold">③</span> Every roadmap change comes with a reason you can read</li>
            <li className="flex gap-3 items-center"><span className="text-[#FF8A24] font-bold">④</span> SAKHA mentors step in with a complete case report</li>
          </ul>
        </div>
      </section>

      <section 
        className="p-6 lg:p-14 flex items-center justify-center relative overflow-hidden bg-cover bg-center"
        style={{
          backgroundImage: `radial-gradient(ellipse at 50% 50%, rgba(7, 19, 29, 0.50) 0%, rgba(5, 14, 22, 0.80) 100%), url('/background.jpg')`
        }}
      >
        <form onSubmit={go} className="card p-8 lg:p-10 w-full max-w-md space-y-4.5 shadow-2xl backdrop-blur-2xl bg-[rgba(16,26,36,0.85)] border border-[rgba(210,225,235,0.22)]">
          <div>
            <div className="eyebrow">Get started</div>
            <h2 className="text-2xl font-extrabold text-white heading-glow mt-1">
              {real && mode === 'signin' ? 'Sign in to SAARTHI' : 'Create your learner profile'}
            </h2>
          </div>

          {real && (
            <div className="flex gap-2 p-1 rounded-xl bg-[rgba(10,20,30,0.5)] border border-[rgba(210,225,235,0.12)]" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'signup'}
                className={`btn btn-sm flex-1 text-xs ${mode === 'signup' ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setMode('signup')}
              >
                Create account
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'signin'}
                className={`btn btn-sm flex-1 text-xs ${mode === 'signin' ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setMode('signin')}
              >
                Sign in
              </button>
            </div>
          )}

          {real && !supabaseConfigured && (
            <p className="text-xs bg-[rgba(255,83,100,0.12)] border border-[rgba(255,83,100,0.3)] text-red-200 rounded-lg p-3 font-semibold">
              Supabase keys are missing in the browser build: add VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY to frontend/.env.local.
            </p>
          )}

          {notice && (
            <p className="text-sm bg-[rgba(77,157,255,0.15)] border border-[rgba(77,157,255,0.3)] text-blue-200 rounded-lg p-3 font-semibold" role="status">
              {notice}
            </p>
          )}

          {real && (
            <>
              <label className="block text-sm font-semibold text-slate-200 desc-glow">
                Email
                <input
                  className="input mt-1.5"
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  autoComplete="email"
                />
              </label>
              <label className="block text-sm font-semibold text-slate-200 desc-glow">
                Password
                <input
                  className="input mt-1.5"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                />
              </label>
            </>
          )}

          {(!real || mode === 'signup') && (
            <>
              <label className="block text-sm font-semibold text-slate-200 desc-glow">
                Your name
                <input
                  className="input mt-1.5"
                  required
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. Priya Sharma"
                  autoFocus={!real}
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm font-semibold text-slate-200 desc-glow">
                  Age
                  <input
                    className="input mt-1.5"
                    type="number"
                    min={10}
                    max={100}
                    required
                    value={age}
                    onChange={e => setAge(parseInt(e.target.value || '0'))}
                  />
                </label>
                <label className="block text-sm font-semibold text-slate-200 desc-glow">
                  Language
                  <select
                    translate="no"
                    className="input mt-1.5"
                    value={language}
                    onChange={e => setLanguage(e.target.value)}
                  >
                    <option value="english">English</option>
                    <option value="hindi">हिन्दी (Hindi)</option>
                    <option value="hinglish">Hinglish</option>
                  </select>
                </label>
              </div>
              {age > 0 && age < 18 && (
                <p className="text-xs bg-[rgba(255,181,46,0.12)] border border-[rgba(255,181,46,0.3)] text-[#FFB52E] rounded-lg p-2.5">
                  Under 18? You can use every learning feature. Mentor sessions need a parent or guardian's approval first.
                </p>
              )}
            </>
          )}

          <button
            className="btn btn-orange w-full py-3 text-base font-semibold shadow-[0_6px_20px_rgba(255,120,30,0.28)]"
            disabled={busy || (real && mode === 'signin' ? !email || !password : !name.trim() || age < 10 || (real && (!email || password.length < 8)))}
          >
            {busy ? 'Please wait…' : real && mode === 'signin' ? 'Sign in →' : real ? 'Create account →' : 'Continue →'}
          </button>

          {real && (
            <>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <span className="h-px flex-1 bg-[rgba(210,225,235,0.12)]" />
                or
                <span className="h-px flex-1 bg-[rgba(210,225,235,0.12)]" />
              </div>
              <button
                type="button"
                className="btn btn-secondary w-full py-2.5 flex items-center justify-center gap-2"
                disabled={busy}
                onClick={google}
              >
                <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z"/><path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 010-9.4l-7.9-6.1a24 24 0 000 21.6l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.9 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z"/></svg>
                Continue with Google
              </button>
              <p className="text-[11px] text-slate-400 desc-glow">
                With Google we will ask for your age once, because learners under 18 get extra protection.
              </p>
            </>
          )}

          {!real && (
            <p className="text-[11px] text-slate-400 desc-glow flex items-center gap-1.5 flex-wrap">
              Demo sign-in (no password). <DemoBadge label="mock auth" title="Real sign-in is switched on with SAARTHI_AUTH=supabase." />
            </p>
          )}

          {health && !health.ok && (
            <p className="text-xs bg-[rgba(255,83,100,0.12)] border border-[rgba(255,83,100,0.3)] text-red-200 rounded-lg p-2.5 font-semibold">
              Can't reach the SAARTHI API. Start the backend (see README) and refresh.
            </p>
          )}
        </form>
      </section>
    </div>
  )
}
